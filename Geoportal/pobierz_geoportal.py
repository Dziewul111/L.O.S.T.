#!/usr/bin/env python3
"""Pobieranie ortofotomapy GUGiK przez WCS 1.0.0 do kafli GeoTIFF."""
import argparse
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import requests
import rasterio
from pyproj import Transformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SERVICE = 'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/StandardResolution'
NS = {'wcs': 'http://www.opengis.net/wcs'}


def download(session, params, target, width, height, bounds):
    """Zapis atomowy, kontrola błędów XML i georeferencji przed zapisem."""
    for attempt in range(3):
        temporary = None
        try:
            with session.get(SERVICE, params=params, stream=True, timeout=(20, 180)) as response:
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.part', delete=False) as f:
                    temporary = Path(f.name)
                    for chunk in response.iter_content(1024 * 1024):
                        f.write(chunk)
            with temporary.open('rb') as f:
                header = f.read(1024)
            if header[:4] not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
                raise RuntimeError('Serwer nie zwrócił TIFF: ' + header.decode('utf-8', errors='replace')[:700])
            with rasterio.open(temporary) as ds:
                if ds.crs is None or ds.crs.to_epsg() != 2180:
                    raise RuntimeError('Niepoprawny układ współrzędnych w TIFF.')
                if (ds.width, ds.height) != (width, height):
                    raise RuntimeError('Niepoprawne wymiary TIFF.')
                tolerance = max((bounds[2] - bounds[0]) / width,
                                (bounds[3] - bounds[1]) / height) * 0.01
                if any(abs(a - b) > tolerance for a, b in zip(ds.bounds, bounds)):
                    raise RuntimeError('Zasięg TIFF różni się od zamówionego.')
                # Odczyt każdego bloku wykrywa też uszkodzony lub ucięty plik.
                for _, window in ds.block_windows(1):
                    ds.read(window=window)
            os.replace(temporary, target)
            return
        except (requests.RequestException, RuntimeError, rasterio.errors.RasterioError) as exc:
            if attempt == 2:
                raise
            print(f'Ponowienie pobrania: {exc}', file=sys.stderr)
            time.sleep(2 ** (attempt + 1))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bbox', nargs=4, type=float, required=True,
                   metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'),
                   help='Granice: zachód południe wschód północ; domyślnie długość/szerokość w stopniach.')
    p.add_argument('--crs', choices=['EPSG:4326', 'EPSG:2180'], default='EPSG:4326',
                   help='Dla EPSG:2180 podaj easting_min northing_min easting_max northing_max w metrach.')
    p.add_argument('--resolution', type=float, default=0.5, help='Wielkość piksela w metrach (domyślnie 0.5).')
    p.add_argument('--tile-pixels', type=int, default=2048, help='Maksymalny bok kafla w pikselach (1–4096).')
    p.add_argument('--output', type=Path, default=Path('ortofotomapa'))
    p.add_argument('--overwrite', action='store_true', help='Zastąp istniejące pliki o tych samych nazwach.')
    p.add_argument('--dry-run', action='store_true', help='Pokaż rozmiar pobrania bez łączenia z serwerem.')
    args = p.parse_args()
    west, south, east, north = args.bbox
    if not all(math.isfinite(v) for v in args.bbox) or west >= east or south >= north:
        p.error('BBOX musi zawierać skończone liczby i spełniać west < east oraz south < north.')
    if not math.isfinite(args.resolution) or args.resolution <= 0:
        p.error('Rozdzielczość musi być dodatnią, skończoną liczbą.')
    if not 1 <= args.tile_pixels <= 4096:
        p.error('--tile-pixels musi należeć do zakresu 1–4096.')
    if args.crs == 'EPSG:4326':
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            p.error('Niepoprawne długości lub szerokości geograficzne.')
        transformer = Transformer.from_crs(4326, 2180, always_xy=True)
        bounds = transformer.transform_bounds(west, south, east, north, densify_pts=21)
    else:
        bounds = tuple(args.bbox)
    if not all(math.isfinite(v) for v in bounds):
        p.error('Nie można przeliczyć tego obszaru do EPSG:2180.')
    xmin, ymin, xmax, ymax = bounds
    # Orientacyjny zasięg z DescribeCoverage; nie gwarantuje pokrycia zdjęciami.
    if xmin < 160828 or ymin < 98928 or xmax > 876030 or ymax > 796522:
        p.error('Obszar wykracza poza zasięg usługi ortofotomapy Polski.')
    res = args.resolution
    width = math.ceil((xmax - xmin) / res)
    height = math.ceil((ymax - ymin) / res)
    cols = math.ceil(width / args.tile_pixels)
    rows = math.ceil(height / args.tile_pixels)
    print(f'{width} × {height} pikseli, {rows * cols} plików; RGB bez kompresji ok. {width * height * 3 / 1e6:.1f} MB.')
    if args.dry_run:
        return
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.overwrite:
        for row in range(rows):
            for col in range(cols):
                target = args.output / f'orto_r{row:04d}_c{col:04d}.tif'
                if target.exists():
                    p.error(f'Plik już istnieje: {target}. Wybierz inny folder albo --overwrite.')
    with requests.Session() as session:
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retry))
        response = session.get(SERVICE, params={'SERVICE': 'WCS', 'VERSION': '1.0.0',
                                               'REQUEST': 'GetCapabilities'}, timeout=(20, 60))
        response.raise_for_status()
        root = ET.fromstring(response.content)
        names = root.findall('.//wcs:CoverageOfferingBrief/wcs:name', NS)
        if len(names) != 1 or not names[0].text:
            raise RuntimeError('Usługa nie udostępnia jednej jednoznacznej warstwy ortofotomapy.')
        for row in range(rows):
            for col in range(cols):
                w = min(args.tile_pixels, width - col * args.tile_pixels)
                h = min(args.tile_pixels, height - row * args.tile_pixels)
                left = xmin + col * args.tile_pixels * res
                top = ymax - row * args.tile_pixels * res
                box = (left, top - h * res, left + w * res, top)
                params = {'SERVICE': 'WCS', 'VERSION': '1.0.0', 'REQUEST': 'GetCoverage',
                          'COVERAGE': names[0].text, 'CRS': 'EPSG:2180',
                          'RESPONSE_CRS': 'EPSG:2180', 'FORMAT': 'GEOTIFF',
                          'BBOX': ','.join(f'{v:.8f}' for v in box), 'WIDTH': w, 'HEIGHT': h}
                target = args.output / f'orto_r{row:04d}_c{col:04d}.tif'
                print(f'[{row * cols + col + 1}/{rows * cols}] {target}', flush=True)
                download(session, params, target, w, h, box)
    print('Gotowe. Pliki GeoTIFF można otworzyć np. w QGIS.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException,
            rasterio.errors.RasterioError, ET.ParseError) as exc:
        sys.exit(f'Błąd: {exc}')
    except KeyboardInterrupt:
        sys.exit('Przerwano pobieranie.')
