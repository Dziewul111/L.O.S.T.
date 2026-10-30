# Pobieranie ortofotomapy Geoportalu do GeoTIFF

Skrypt pobiera ortofotomapę RGB Polski z oficjalnej usługi WCS GUGiK. To obraz dostępny jako ortofotomapa, a nie surowe sceny satelitarne Sentinel/Landsat. Nie wybiera daty wykonania zdjęć; pobiera mozaikę aktualnie udostępnianą przez usługę, która może obejmować zdjęcia z różnych lat.

## Instalacja

Wymagany Python 3.10 lub nowszy. Zapisz skrypt i requirements.txt w jednym folderze, otwórz w nim terminal i uruchom:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows: zamiast `source` użyj `.venv\Scripts\activate` (wiersz poleceń), a do utworzenia środowiska możesz użyć `py -m venv .venv`.

## Pobieranie

Przykładowy fragment Warszawy:

```sh
python pobierz_geoportal.py --bbox 21.00 52.22 21.02 52.24 --resolution 0.5 --output warszawa
```

Kolejność granic to **zachód południe wschód północ**, czyli długość, szerokość, długość, szerokość geograficzna. Stosuj kropki dziesiętne. Zastąp współrzędne granicami swojego obszaru.

`--resolution 0.5` oznacza piksel o boku 0,5 m. Mniejsza wartość zwiększa pliki i nie gwarantuje większej szczegółowości niż materiał źródłowy.

Przed dużym pobraniem sprawdź liczbę plików i szacowaną objętość:

```sh
python pobierz_geoportal.py --bbox 21.00 52.22 21.02 52.24 --resolution 0.5 --dry-run
```

Możesz także podać granice w metrach w PL-1992:

```sh
python pobierz_geoportal.py --crs EPSG:2180 --bbox 637000 486000 637500 486500 --output fragment
```

Tutaj kolejność to **easting_min northing_min easting_max northing_max** (oś wschodnia przed północną, niezależnie od oznaczeń X/Y w innych programach).

## Wynik i ograniczenia

- Pliki `orto_r0000_c0000.tif` itd. zawierają georeferencję EPSG:2180 i można je wczytać razem do QGIS. Skrypt nie scala ich w jeden plik.
- Domyślny kafel ma maksymalnie 2048 × 2048 pikseli. Jeśli serwer odrzuca pobranie, spróbuj `--tile-pixels 1024`.
- Obszar w stopniach jest przeliczany na otaczający prostokąt w PL-1992. Wynik może nieznacznie wychodzić poza wskazane granice; ostatni piksel również zaokrągla zasięg w górę. To nie jest przycięcie do dokładnego wielokąta.
- Zasięg usługi nie gwarantuje obecności zdjęć w każdym miejscu. Puste obszary mogą pozostać w poprawnym TIFF.
- Istniejące pliki powodują zatrzymanie przed pobieraniem. Wybierz nowy folder albo dodaj `--overwrite`, by świadomie je zastąpić. Skrypt nie wznawia pobierania od ostatniego kafla.
- Plik jest zapisywany pod docelową nazwą dopiero po sprawdzeniu wymiarów, zasięgu, układu współrzędnych i odczytu danych. Pobieranie wymaga internetu i dostępności usługi.

Źródła:
- https://www.geoportal.gov.pl/pl/usluga/uslugi-pobierania-wcs/
- https://www.geoportal.gov.pl/pl/dane/ortofotomapa-orto/
- https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/StandardResolution?SERVICE=WCS&REQUEST=GetCapabilities&VERSION=1.0.0
