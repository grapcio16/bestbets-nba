# BestBets — instrukcja dla Codexa (wersja testowa V2)

## Cel
Wyjaśnić i usunąć efekt oddalonego dashboardu, który po wejściu na stronę stopniowo się powiększa. Zdarzały się również czarne ekrany w Operze po wcześniejszych modyfikacjach.

## Stan
- **Nie zmieniaj produkcyjnej gałęzi `main` i nie modyfikuj `app.py` bez osobnej akceptacji.**
- Testowa gałąź: `experiment/bestbets-iframe-free-v2-20261111`.
- Bezpieczny punkt wejścia do testowania: `preview_v2.py`.
- Nowy frontend: `bestbets_v2_preview.py`. Wykorzystuje istniejące HTML/CSS i JavaScript z `bestbets_reference_frontend/index.html`, lecz osadza je jako Streamlit Components V2 bez iframe. SVG `viewBox` skaluje cały dashboard natywnie, bez pętli wysokości.
- Zachowane dane i algorytmy: `bestbets_custom_screen._research`, istniejące źródła NBA/ESPN, sześć dolnych kafelków, wyszukiwarka, rynki PTS/REB/AST/3PM/PRA, aktualny wygląd i neony.

## Lokalny test na Windows
1. Sklonuj repozytorium GitHub `grapcio16/bestbets-nba` lub otwórz istniejący checkout.
2. `git fetch origin`
3. `git checkout experiment/bestbets-iframe-free-v2-20261111`
4. `python -m pip install -r requirements.txt`
5. `python -m pip install "streamlit>=1.59,<2"`
6. `python -m streamlit run preview_v2.py`
7. Otwórz podany adres localhost w **Operze**.

## Zadania testowe
- Zrób zapis ekranu w momencie pierwszego widocznego renderu oraz 1, 3 i 6 sekund po otwarciu. Zmierz bounding box dashboardu; nie powinno być skoków wielkości.
- Przeładuj Ctrl+F5, sprawdź rozdzielczości 1664×900, 1366×768, 1920×1080 oraz powiększenie Opery 100%.
- Sprawdź w konsoli błędy JS i nieudane żądania.
- Kliknij sześć dolnych modułów; potwierdź, że nawigacja wraca do Player Props.
- Zbadaj zapytanie Player Props przy prawdziwym połączeniu ze źródłami NBA; nie podstawiaj fikcyjnych statystyk ani rankingów do aplikacji.
- Porównaj wygląd do grafiki referencyjnej; nie zmieniaj kolorów, typografii, neonu, ułożenia paneli ani kodu modelu statystycznego bez zgody.
- Przygotuj Pull Request z wynikami oraz zrzutami, ale **nie scalaj do `main`**.

## Dostępne CI
`test_v2_browser_preview.py` + workflow `.github/workflows/iframe-free-v2-preview.yml` uruchamiają Chromium, weryfikują brak iframe i stabilność wymiarów.

## Diagnoza bazowa
Poprzedni frontend v1 po montowaniu miał w `resize()` obliczenie skali z aktualnej wysokości iframe i zgłaszał `streamlit:setFrameHeight` na podstawie tej skali. Tworzyło to ryzyko sprzężenia zwrotnego podczas startu (stopniowe przybliżanie). Wersja V2 nie wykorzystuje iframe.
