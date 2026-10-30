#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "Brakuje środowiska Python. Zajrzyj do README.md."
  read "odpowiedz?Naciśnij Enter, aby zakończyć."
  exit 1
fi
source .venv/bin/activate
printf '\nGEOportal — pobieranie zdjęć TIFF\n\n'
printf 'Wpisuj polecenia poniżej. Pliki zapiszą się w tym folderze.\n\n'
printf 'Przykład (Warszawa):\n'
printf 'python pobierz_geoportal.py --bbox 21.00 52.22 21.02 52.24 --resolution 0.5 --output warszawa\n\n'
printf 'Granice: zachód południe wschód północ. Używaj kropek dziesiętnych.\n'
printf 'Pomoc: python pobierz_geoportal.py --help\n'
printf 'Zakończenie: exit\n\n'
exec /bin/zsh -f -i
