# BestBets V2 — responsive full-width

Zmiana dotyczy wyłącznie preview. Bazą jest aktualny stan V2 z PR #45,
`1efb477`, łącznie z późniejszym rozszerzeniem tła. Nowy PR jest osobny,
skierowany do gałęzi `fix/stable-v2-startup-20261111`, żeby jego diff pokazywał
samą przebudowę responsive. `app.py`, produkcyjny HTML, źródła danych i modele
nie zostały zmienione. Nie wykonano wdrożenia ani scalenia.

## Jak działa układ

- Usunięto główny SVG/foreignObject, proporcję 1231:691 i skalowanie aplikacji.
  Zawartość jest zwykłym HTML w izolowanym komponencie Streamlit V2.
- Root zajmuje szerokość okna; natywny pasek przewijania rezerwuje 10 px w
  testowanym Chromium. Nie ma ograniczenia szerokości wynikającego z wysokości.
- CSS Grid dzieli aplikację na sidebar i `minmax(0,1fr)`. Sidebar ma 200 px
  na desktopie, 176 px na mniejszych ekranach i 64 px jako pasek ikon telefonu.
  Etykiety pozostają w drzewie dostępności, a wszystkie przyciski nadal działają.
- Wyszukiwarka, podpowiedzi, hero, kontrolki i BestBets Take wypełniają kolumnę
  contentu. Wykres dostaje wolne miejsce obok panelu statystyk 412 px.
  Poniżej 1200 px panel statystyk przechodzi pod wykres.
- Dolne moduły to równe kolumny Grid: sześć od 1440 px, trzy od 901 px,
  dwie od 641 px, jedna na telefonie. Karta i jej podpis nawigacyjny pozostają
  razem przy zawijaniu. Zachowano naprzemienne niebieskie i pomarańczowe neony.
- Na telefonie i niskim oknie strona przewija się pionowo. Kontrolki i fonty
  nie są pomniejszane, a dolne sekcje nie są obcinane do wysokości ekranu.
- Host komponentu jest przewijalnym kontenerem przypiętym do okna. Pozwala to
  ominąć opóźnione marginesy Streamlit; wewnątrz działa naturalny układ o
  minimalnej wysokości okna, bez wymuszania wysokości zawartości lub proporcji.

SVG pozostał **wyłącznie wewnątrz wykresu**. Jego viewBox odpowiada rzeczywistym
wymiarom panelu w pikselach. Osie, słupki i etykiety są rysowane dla tej
szerokości, więc tekst nie jest rozciągany. Obserwator rozmiaru śledzi tylko
wykres i nie zapisuje rozmiarów dashboardu ani nie negocjuje wysokości iframe.
Po aktualizacji danych przez Streamlit obserwator jest ponownie podłączany;
obsługi kliknięć pozostają związane raz.

Kolory, font Inter/Arial, gradienty, obramowania, animacje przycisków, słupków,
portretu i metryk pochodzą z dotychczasowej wersji. Nowy `responsive.css` ma
niezależną geometrię, dzięki czemu produkcyjny dokument v1 pozostaje nietknięty.
Routing sześciu kafelków i menu, parser oraz `_research` są zachowane.
Zakładki, które wcześniej były zapowiedziami, nadal są zapowiedziami.

## Dokładna lista plików w tym PR

| Plik | Zmiana |
|---|---|
| `bestbets_v2_preview.py` | Zwykły HTML zamiast app-SVG; nowy CSS, parowanie kart z podpisami, płynny wykres i cykl życia obserwatora |
| `bestbets_reference_frontend/responsive.css` | Nowy arkusz premium z Grid/Flex i breakpointami |
| `test_v2_browser_preview.py` | Szerokość rzeczywistych paneli, klatki startu, szerokie monitory, zawijanie, przewijanie, routing i aktualizacje |
| `test_scaling_evidence.py` | Porównanie stylów zamiast nieaktualnego wymogu identycznych współrzędnych; statyczny shell bez JS; konfigurowalne URL |
| `.github/workflows/iframe-free-v2-preview.yml` | Testy responsive i unittest, Streamlit 1.59/latest, obsługa PR skierowanego do gałęzi V2 |
| `docs/RESPONSIVE_V2_FULL_WIDTH.md` | Ten opis i instrukcja testowania |
| `docs/qa-responsive-v2-20261111/results-summary.json` | Pomiary i ograniczenia testów |
| `docs/qa-responsive-v2-20261111/before-2560.png` | Poprzednia plansza V2 przy 2560×1080 |
| `docs/qa-responsive-v2-20261111/after-2560.png` | Płynny układ przy tej samej rozdzielczości |
| `docs/qa-responsive-v2-20261111/after-1920.png` | Desktop 1920×1080 |
| `docs/qa-responsive-v2-20261111/after-mobile.png` | Telefon 390×844, początek przewijanej strony |
| `docs/qa-responsive-v2-20261111/live-player-props.png` | Wykres z rzeczywistymi danymi po zmianie rozmiaru |

## Testy

Lokalnie: Python 3.12.14, Playwright 1.62.0, Chromium 151.0.7922.34,
Streamlit 1.59.0 oraz 1.67.0, domyślne powiększenie 100%.

- 196/196 regresji Python.
- Po 13 startów/przeładowań na obu wersjach Streamlit, łącznie 10260 klatek
  pomiarowych. Wymiary od pierwszej klatki do 6 s nie zmieniały się.
- Rozmiary: 1664×900, 1366×768, 1920×1080, 2560×1080, 3440×1440,
  1024×768, 768×1024, 390×844, 320×740, 844×390.
- Trzy desktopowe przeładowania z wyłączonym cache HTTP; zrzuty w 0/1/3/6 s.
- Sidebar i content zajmują dostępną szerokość, hero i dolny grid dochodzą do
  tej samej prawej krawędzi. Brak poziomego overflow. Sekcje są osiągalne
  przewijaniem, bez obcinania. Równe szerokości kart i poprawne stosy paneli.
- Widoczny tekst, panele i jasne piksele na każdym zrzucie; brak iframe oraz
  głównego SVG, brak transformacji lub aspect-ratio aplikacji.
- Wszystkie sześć kafelków i powrót do Player Props, rynki PTS/REB/AST/3PM/PRA,
  zakresy L5/L10/L15/Season i kolejne identyczne odpowiedzi walidacji.
- Porównano 9 elementów z v1: zgodne rodziny fontu, kolory, gradienty, obramowania
  i cienie. Nie wymagamy dawnych współrzędnych, ponieważ układ jest teraz płynny.
- Statyczny shell wypełnia szerokość także bez uruchomienia JS komponentu.

| Okno | Szerokość root | Main | Wykres | Statystyki |
|---|---:|---:|---:|---:|
| 1664×900 | 1654 px | 1454 px | 994 px | 412 px |
| 1920×1080 | 1910 px | 1710 px | 1250 px | 412 px |
| 2560×1080 | 2550 px | 2350 px | 1890 px | 412 px |
| 3440×1440 | 3430 px | 3230 px | 2770 px | 412 px |

Wykres z rzeczywistymi danymi Nikoli Jokicia miał 1224 px obszaru rysowania
przy 1920×1080 i 1864 px przy 2560×1080. Wartości statystyk po zmianie okna
pozostały takie same. Backend dostarczył 14 występów; sprawdzono wszystkie
pięć rynków, L5/L10/L15/Season i Home/Away. Nie użyto fikcyjnych statystyk.

Ograniczenia: środowisko przeglądarkowe nadal odrzuca certyfikat zdjęcia ESPN
(`ERR_CERT_AUTHORITY_INVALID`); portretu nie ma na zrzucie live. Nie wyłączano
weryfikacji TLS. Testy geometrii i danych nie zależą od tego obrazka.
Nie wykonano testu Opery na Windows; Chromium nie jest jego zamiennikiem.
Wyniki dotyczą lokalnych aplikacji Streamlit, nie publicznego wdrożenia.

## Jak uruchomić preview

W checkout repozytorium, w terminalu:

```bash
git fetch origin
git switch feature/responsive-v2-full-width-20261111
python -m pip install -r requirements-preview.txt
python -m streamlit run preview_v2.py --server.port 8501
```

Otwórz **http://localhost:8501**. Ustaw 100%, wykonaj Ctrl+F5 i porównaj
1920×1080 z 2560×1080. Sidebar pozostaje tej samej szerokości, a wyszukiwarka,
hero, wykres i karty rozszerzają się. Zwęź okno do telefonu: sekcje przechodzą
do kolejnych rzędów i można przewinąć stronę do wszystkich sześciu kart.
Wyszukaj zawodnika, zmień rynek, okres i rozmiar okna; liczby powinny pozostać
zgodne z tą samą analizą.

Automatyczne testy, przy uruchomionym preview:

```bash
python -m pip install playwright
python -m playwright install chromium
python -m unittest discover -v
python test_v2_browser_preview.py --url http://127.0.0.1:8501/
```

Artefakty trafiają do `work/v2-browser/`. Opcjonalny `--live` wykonuje prawdziwe
zapytanie NBA/ESPN i wymaga dostępu do źródeł i obrazków. Test porównania motywu
`test_scaling_evidence.py` wymaga dodatkowo `app.py` uruchomionego na porcie
8502. CI zapisuje zrzuty wszystkich rozdzielczości i pełne pomiary klatek.

### Zrzuty do przeglądu

[Przed, 2560×1080](qa-responsive-v2-20261111/before-2560.png) ·
[Po, 2560×1080](qa-responsive-v2-20261111/after-2560.png) ·
[Po, 1920×1080](qa-responsive-v2-20261111/after-1920.png) ·
[Telefon](qa-responsive-v2-20261111/after-mobile.png) ·
[Rzeczywista analiza](qa-responsive-v2-20261111/live-player-props.png) ·
[Pomiary JSON](qa-responsive-v2-20261111/results-summary.json)
