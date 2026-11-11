# BestBets — audyt startu i poprawka V2

Stan: 11 listopada 2026. Punkt odniesienia produkcji: `76e6b46`
(przywrócenie v10.1). Punkt wyjścia eksperymentu: `a79de39`.

Poprawka działa w **osobnym `preview_v2.py`**. Nie zmieniono `app.py`,
produkcyjnego HTML, algorytmów ani źródeł NBA. Nie wykonano wdrożenia.
Scalenie tego PR samo w sobie nie przełącza publicznej aplikacji na V2.

## 1. Przyczyna skalowania

Publiczny punkt wejścia to `app.py → bestbets_custom_screen.main()`.
Frontend jest dokumentem `bestbets_reference_frontend/index.html` w komponencie
Streamlit v1, czyli w iframe. Wzorcowy dashboard ma 1231 × 691 px.

Funkcja `resize()` używa wysokości **bieżącego iframe**, a nie okna użytkownika:

```text
s = min(szerokość_iframe / 1231, max(0.25, wysokość_iframe / 691))
wysokość_zgłoszona_do_Streamlit = ceil(691 × s) + 2
```

Kiedy ograniczeniem jest wysokość, następna wysokość wynosi około `H + 2`.
Streamlit zmienia iframe, przeglądarka wywołuje `resize`, frontend ponownie
oblicza skalę i zgłasza kolejną wysokość. Przy początkowym iframe 150 px działa
też dolne ograniczenie do 240 px. Powstaje widoczne stopniowe powiększanie.
Zależne od czasu załadowania reguły rodzica `height:100dvh!important` mogą
przerwać pętlę; nie stanowią jednak niezawodnego protokołu inicjalizacji.

`test_scaling_evidence.py` odtwarza tę zależność na **niezmienionym** frontendzie
v1 w kontrolowanym hoście obsługującym `streamlit:setFrameHeight`. Pierwsze
20 kolejnych zgłoszeń różni się dokładnie o 2 px. To odtworzenie mechanizmu,
nie nagranie z produkcji ani z Opery. Rzeczywisty lokalny punkt wejścia v1
posłużył dodatkowo do porównania wyglądu.

| Czas | Szerokość v1 w kontrolowanym starcie | Szerokość poprawionego V2, 1664×900 |
|---|---:|---:|
| Pierwszy zapis | 431.13 px | 1596.17 px |
| 1 s | 509.50 px | 1596.17 px |
| 3 s | 635.98 px | 1596.17 px |
| 6 s | 810.58 px | 1596.17 px |

Tempo pętli zależy od obsługi komunikatów i obciążenia, więc czasy v1 nie są
uniwersalnym benchmarkiem. Przy wysokości 900 px dashboard zachowuje proporcje
i ma 896 px wysokości; pozostałe miejsce stanowi zatwierdzony margines.

## 2. Co poprawiono w eksperymencie V2

1. **Skala bez negocjowania wysokości.** Natywny SVG `viewBox` i `foreignObject`
   mieszczą istniejący dokument HTML w oknie. Nie ma iframe, `setFrameHeight`,
   pętli `ResizeObserver` ani obliczania skali w JavaScript.
2. **Pierwszy render niezależny od kontenera Streamlit.** Test klatek wykrył
   początkowe 80 px marginesu na ekranie 1920×1080. Host dedykowanego ekranu
   ma teraz `position:fixed; inset:0`, a szerokość SVG wynika z `100vw` i
   `100dvh`. Późniejsze zastosowanie CSS strony nie zmienia skali.
3. **Zgodny wygląd Shadow DOM.** Oryginalne reguły `:root` i `html,body`
   przetłumaczono na `:host`; przywrócono dziedziczenie fontu, koloru i normalnej
   wysokości wiersza. Wcześniejszy eksperyment dziedziczył Source Sans i ciemny
   tekst z motywu Streamlit. Oryginalne kolory, neon, geometria i animacje
   pozostały w niezmienionym źródłowym HTML/CSS.
4. **Poprawny cykl życia V2.** Streamlit zachowuje DOM, lecz ponownie uruchamia
   funkcję JS po zmianie danych. Zdarzenia są wiązane raz, aktualizacje używają
   istniejącego stanu. Każda odpowiedź ma ID żądania, więc również kolejne
   identyczne odpowiedzi kończą ładowanie. Nie mnożą się obsługi kliknięć.
5. **Oddzielne zależności.** `requirements-preview.txt` wymaga Streamlit ≥1.59.
   Produkcyjne `requirements.txt` pozostaje bez zmian.

Nie dodano ukrywania dashboardu do czasu zakończenia JS. Statyczny shell V2
pozostaje widoczny w teście bez uruchamiania skryptu komponentu.

## 3. Czarne ekrany i historia prób

| Zmiana | Ustalenie z historii |
|---|---|
| v10, `c11b431` | Przejście do własnego komponentu HTML v1; backend zachowany |
| v10.1, `43ef078` | Dopasowanie obu osi, sześć kafelków, animacje i synchronizacja wyszukiwania |
| v10.3, `989054d` | Dodano `visibility:hidden` i klasę `ready` ustawianą przez JS; wycofano w `9edd62f` |
| v10.4, `79e877e` | Skala wyliczana w `<head>`, nadal zależna od wysokości iframe; wycofano w `0ad69ae` |
| v10.5, `a177bed` | Heurystyki wysokości startowej i wymiarów ekranu; wycofano w `76e6b46` |
| V2, `1ae7525`–`a79de39` | Osobny eksperyment bez iframe, punkt wejścia, test i brief |

W v10.3 błąd JS przed dodaniem `ready` zostawiał cały shell ukryty. Jest to
konkretny mechanizm mogący dać pusty ekran. Bez logów z wcześniejszych sesji
Opery nie można przypisać mu wszystkich zgłoszonych czarnych ekranów.
Nie potwierdzono ani nie wykluczono osobnej regresji renderera Opery/SVG.

## 4. Testy i dowody

Python 3.12.14, Playwright 1.62.0, Chromium 151.0.7922.34, Linux,
`device_scale_factor=1` i domyślne powiększenie 100%.

| Sprawdzenie | Wynik |
|---|---|
| Streamlit 1.67.0 | 9 startów/przeładowań, 3480 zmierzonych klatek; brak zmian wymiarów |
| Streamlit 1.59.0 | 9 startów/przeładowań, 3349 zmierzonych klatek; brak zmian wymiarów |
| Rozdzielczości | 1664×900, 1366×768, 1920×1080, 1231×691, 390×844, 844×390 |
| Przeładowania | Trzy rozmiary desktopowe, w Chromium wyłączony cache HTTP |
| Zmiana rozmiaru okna | Wszystkie sześć rozmiarów, komplet paneli i sześć kafelków w oknie |
| Puste/czarne powierzchnie | Dodatnie wymiary, widoczny tekst i panele, test jasnych pikseli każdego zrzutu |
| Nawigacja | Sześć dolnych kafelków, każdy ekran i powrót do Player Props |
| Kontrolki | PTS/REB/AST/3PM/PRA, L5/L10/L15/Season, walidacja pustego zapytania |
| Aktualizacje serwera | Trzy kolejne identyczne błędy walidacji; loader kończy pracę; jeden klik = +0.5 |
| Konsola i sieć lokalnej macierzy | 0 błędów JS, 0 błędów konsoli, 0 nieudanych żądań, 0 HTTP ≥400 |
| Zgodność wizualna | 9 elementów: identyczne style i współrzędne; 0% różnych pikseli przy 1231×691 |
| Regresje Python | 196/196; zaktualizowano przestarzałą asercję punktu wejścia v9 |

Test `--live` wykonał prawdziwe wyszukiwanie `Nikola Jokic over 25.5 points`.
Backend zwrócił **14 występów**, źródło `ESPN sezon: gamelog + zweryfikowane
boxscore`. Wszystkie pięć rynków miało dane, zakresy dały odpowiednio 5/10/14/14
słupków, a średnie Home/Away nie były puste. Sprawdzono animację wykresu
oraz `prefers-reduced-motion`. Nie użyto fikcyjnych statystyk.

**Ograniczenie testu live:** cały przebieg zakończył się błędem rygorystycznej
kontroli konsoli: Chromium w tym środowisku odrzuca certyfikat obrazka
`a.espncdn.com/.../3112335.png` (`ERR_CERT_AUTHORITY_INVALID`, 9 żądań).
Funkcjonalne asercje danych przeszły, błędów wykonania JS nie było. Na zrzucie
nie ma portretu. Nie wyłączano sprawdzania TLS. Ten sam problem certyfikatu
uniemożliwił pomiar publicznego URL w Chromium; wyniki skalowania dotyczą
lokalnych, rzeczywistych aplikacji Streamlit.

Opera na Windows wymaga osobnego testu przed akceptacją. Playwright Chromium
nie jest dowodem testu Opery. Dodatkowa próba Firefox w środowisku chmurowym
nie uruchomiła renderera (`/proc/self/uid_map: EROFS`, błąd SWGL); nie zaliczono
jej jako testu przeglądarkowego. Mobilne rozmiary potwierdzają proporcjonalne
dopasowanie istniejącego dashboardu, nie nowy układ telefoniczny.

### Zrzuty

Kontrolowane odtworzenie v1: [start](qa-startup-20261111/v1-feedback-0s.png),
[1 s](qa-startup-20261111/v1-feedback-1s.png),
[3 s](qa-startup-20261111/v1-feedback-3s.png),
[6 s](qa-startup-20261111/v1-feedback-6s.png).

Poprawiony V2: [start](qa-startup-20261111/v2-0s.png),
[1 s](qa-startup-20261111/v2-1s.png), [3 s](qa-startup-20261111/v2-3s.png),
[6 s](qa-startup-20261111/v2-6s.png).

Porównanie prawdziwych punktów wejścia przy rozmiarze referencji:
[v1](qa-startup-20261111/v1-reference.png),
[V2](qa-startup-20261111/v2-reference.png).
[Rzeczywiste zapytanie Player Props](qa-startup-20261111/live-player-props.png).
[Wyniki w JSON](qa-startup-20261111/results-summary.json).
CI zapisuje także wszystkie klatki pomiarowe i zrzuty pozostałych rozdzielczości.

## 5. Architektura i stan funkcji

Projekt jest monolitem Python/Streamlit z czystymi modułami obliczeń. Nie ma
osobnego serwera HTTP API, aplikacji React, kont użytkowników ani integracji
Stripe. Kod frontendowy jest obsługiwany przez komponent; Python odpowiada
na zdarzenia wyszukiwania, a wyniki przechowuje w `st.session_state`.

| Warstwa | Główne pliki i rola |
|---|---|
| Publiczna prezentacja | `app.py`, `bestbets_custom_screen.py`, `bestbets_reference_frontend/index.html`: wyszukiwarka, karta, wykres i kontrolki |
| Testowa prezentacja | `preview_v2.py`, `bestbets_v2_preview.py`: ten sam frontend i `_research`, Components V2 |
| Poprzednie pełne ekrany | `mvp_app.py`, `bestbets_v90.py`, `roster_view.py`, `schedule_ui.py`, `simulation_view.py`: kod zachowany, obecnie poza routingiem publicznego komponentu |
| Player Props | `prop_search.py`, `mvp_prop_ui.py`, `season_props.py`, `mvp_player_card.py`: parser, jednoznaczne dopasowanie, pełne historie, częstości i PRA z tych samych występów |
| Dane i katalog | `sources.py`, `espn_player_data.py`, `roster_data.py`, `global_player_catalog.py`, `schedule_data.py`, `simulation_sources.py` |
| Kontekst | `availability_context.py`, `rotation_intelligence.py`, `match_context.py`, `matchup_roster.py`, `dashboard_data.py`, `center_leaderboard.py`, `mvp_data.py` |
| Obliczenia | `core.py`, `simulation_engine.py`, `simulation_lines.py`, `opponent_ratings.py`, `prediction_engine_v2.py`, `quality_engine.py`, `forecast_quality.py` |
| Audyt modeli | `forecast_audit.py`, `model_validation.py`, `player_model_battle.py`, `simulation_backtest.py`, `simulation_data_audit.py` |
| Tracker | `performance_tracker.py`, `tracker_storage.py`, `tracker_postgres.py`, `tracker_automation.py`: append-only prognozy, rozliczanie, SQLite lub opt-in PostgreSQL |
| Opcjonalne narzędzia | `odds_fetcher.py`, `odds_engine.py`, `market_archive.py`, `screenshot_import.py`, `screenshot_ui.py`, `screenshot_cards.py`, `prop_search_ui.py` |
| Styl i zasoby | `mvp_*theme.py`, `premium_theme.py`, `bestbets_v90_theme.py`, `bestbets_v91_fx.py`, `mvp_reference_footer.py`, `simulation_premium.py`, `team_logos.py`, `teams.py`, `viewer_time.py`, `assets/` |

Istotne rozróżnienie: w obecnym HTML funkcja `render()` pokazuje `blank-pane`
dla Centrum, Symulacji, Terminarza, Zawodników i Drużyn. Sześć kafelków działa
nawigacyjnie, lecz nie uruchamia wszystkich starszych ekranów. Sama obecność
silnika 5000 losowań nie oznacza, że publiczny kafelek obecnie go wywołuje.
README opisuje też poprzednie wersje, więc nie jest samodzielną specyfikacją
stanu wdrożenia. Ta poprawka nie rozszerza routingu.

Źródła: oficjalne NBA Stats (`nba_api`) → NBA CDN → jawnie częściowe fallbacki
ESPN; osobny sezonowy gamelog ESPN i boxscore dla Player Props. Terminarz NBA
CDN/ESPN, kontuzje i składy ESPN; The Odds API tylko opcjonalnie z kluczem.
Źródła wykorzystują timeouty, cache plikowy `data/` i `st.cache_data`, metadane
starości oraz komunikaty niedostępności. Nie zakładają pełnego pokrycia tylko
dlatego, że otrzymano odpowiedź. Automatyczny tracker wymaga skonfigurowanego
sekretu PostgreSQL i ma osobny workflow; nie uruchamiano go w tej pracy.

Symulator wymusza dokładnie 5000 losowań, ma powtarzalny seed, wspólny składnik
tempa, szum drużyn i dogrywki bez remisów. To model heurystyczny; historyczny
hit rate i udział wygranych losowań nie są skalibrowanymi szansami zakładu.
Modele kandydackie i badania pozostają oddzielone od modelu domyślnego.

Do osobnego audytu danych: zakres dat sezonu jest zaszyty jako 2026–27,
strefa części ścieżki jako Europe/Warsaw, wykres Season ogranicza render do
20 ostatnich słupków (agregaty nadal korzystają z dostępnej historii),
a komunikaty `notices` z backendu nie są obecnie wyświetlane w komponencie.
Nie zmieniano tych zachowań przy poprawce skalowania.

Testy to głównie `unittest` dla parserów, źródeł, kalibracji, symulacji,
rotacji, Trackera i zachowania UI oraz Playwright dla widoku. Workflowy:
`v7-roster-validation.yml`, `v10-reference-browser.yml`,
`iframe-free-v2-preview.yml`, `tracker-auto.yml`. Rozszerzony workflow V2
sprawdza minimum 1.59.0 i najnowszą zgodną wersję Streamlit, bez dostępu do NBA.

## 6. Uruchomienie i akceptacja

```bash
python -m pip install -r requirements-preview.txt
python -m pip install playwright
python -m playwright install chromium
python -m streamlit run preview_v2.py --server.port 8501
# W drugim terminalu, tylko do porównania:
python -m streamlit run app.py --server.port 8502
# Testy:
python -m unittest discover -v
python test_v2_browser_preview.py
python test_scaling_evidence.py
# Opcjonalnie, rzeczywiste połączenia z dostawcami:
python test_v2_browser_preview.py --live --out work/v2-live
```

Przed publicznym przełączeniem: uruchomić `preview_v2.py` w Operze na Windows,
100%, Ctrl+F5, trzy wymagane rozdzielczości; sprawdzić portret i certyfikaty,
zrzuty 0/1/3/6 s, wyszukiwanie, animacje i wszystkie kafelki. Dopiero po
akceptacji przygotować osobny przegląd zmiany punktu wejścia/deploymentu.

## 7. Proponowany rozwój po akceptacji skalowania

| Etap | Zakres i warunek ukończenia |
|---|---|
| 1. Warstwa wspólna | Oddzielić serwisy danych od renderowania, ujednolicić cache, błędy, pochodzenie i świeżość; testować brak danych bez fikcyjnych zastępstw |
| 2. Centrum | Podłączyć zachowane rankingi, mecze dnia i kontuzje; każdy wpis prowadzi do zweryfikowanej analizy, pokazuje datę i źródło |
| 3. Symulacje | Podłączyć `simulation_view`/serwis silnika do zatwierdzonej nawigacji; 5000 losowań, zakresy wyników, składy, absencje i audyt zapisanych prognoz |
| 4. Terminarz | Dzień lokalny użytkownika, status scheduled/live/final, wyniki i szczegóły meczu; UTC w danych i strefy IANA w prezentacji |
| 5. Zawodnicy | Katalog z aktualnych składów, historia sezonu, L5/L10/L15, Home/Away, wejście do Props i jasna informacja o pokryciu danych |
| 6. Drużyny | Profile, terminarz, W/L, forma, rotacja i defensywa; powiązanie z historią i symulacjami |
| 7. Globalizacja | Słowniki PL/EN, sezon i strefa jako konfiguracja, kontrakty danych i monitoring; osobno uzgodnić czytelny wariant mobilny bez zmiany zatwierdzonego desktopu |
| 8. Konta i abonament | Projekt OIDC, PostgreSQL i uprawnień do planów; następnie osobno zatwierdzony Stripe w trybie testowym, podpisane i idempotentne webhooki, portal klienta i serwerowe sekrety |

Ten PR nie dodaje kont, płatności, kluczy API ani sekretów. Przyszłe dane
płatności i dostęp do funkcji muszą być weryfikowane po stronie serwera.
