# BestBets V10 — oryginalny wygląd bez czarnych boków

Ta gałąź jest **wersją testową**, nieprodukcyjną, od bazowego `main`.

## Dlaczego poprzednie poprawki nie usuwały pasów

Oryginalny interfejs to canvas **1231 × 691** (proporcja 1,7815). Wysokie lub szerokie okna przeglądarki mogą mieć inną proporcję, np. szerokość 1920 px przy wysokości dostępnej około 900 px. W takim przypadku nie da się jednocześnie: (a) wypełnić całej szerokości, (b) zmieścić całej wysokości bez przewijania, (c) zachować proporcji i oryginalnych wymiarów elementów. Poprzedni kod wybierał (b,c), stąd czarne pasy.

Ta wersja wybiera **(a,c)**: pełna szerokość oraz oryginalny wygląd i proporcje. Cała strona może być wyższa od okna i dlatego **przewija się pionowo**. Nie rozciągamy elementów i nie zmieniamy ikon, kolorów, typografii, paneli ani kart.

## Co zmieniono

- `bestbets_reference_frontend/index.html`: tylko funkcja `resize()` (skala z szerokości, bez raportowania wysokości iframe).
- `bestbets_custom_screen.py`: tylko CSS **zewnętrznego iframe** (`aspect-ratio: 1231 / 691; height: auto` zamiast ograniczenia do `100dvh`).
- Pozostały HTML/CSS UI, backend danych NBA, animacje, logika wyszukiwania, `app.py` — nietknięte.
- `test_v10_startup_no_feedback.py`: porównanie pikseli do oryginalnego wyglądu oraz test szerokości i pierwszych klatek w Playwright.
- CI: `.github/workflows/v10-original-ui-startup-qa.yml`.

## Test użytkownika bez naruszania publicznej strony

W Streamlit Community Cloud utwórz osobną testową aplikację:

- Repository: `grapcio16/bestbets-nba`
- Branch: `fix/v10-original-ui-full-width-scroll-20261111`
- Main file path: `app.py`

Otwórz w Operze na Windows przy 100% zoomie; sprawdź:
1. Czy nie ma czarnych pionowych pasów na żadnym z boków canvas.
2. Czy obraz nie przybliża się podczas uruchamiania i Ctrl+F5.
3. Czy można **przewinąć w dół**, aby zobaczyć cały pasek sześciu kafelków i stopkę.
4. Czy dane, wyszukiwanie, strony menu i animacje działają identycznie.

Zastrzeżenie: Testy Chromium/Playwright nie zastępują ręcznego testu Opery. Żadnego `Merge` bez akceptacji użytkownika.
