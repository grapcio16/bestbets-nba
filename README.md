# BestBets — NBA Intelligence v6.3

**Rozszerzenie v6.2 pod telefon i publiczny hosting.**

- Interfejs responsywny, sidebar adaptacyjny, czytelniejsze karty i tabele na malym ekranie.
- Nowa zakladka **Telefon i publikacja** ze sciezka GitHub → Streamlit Community Cloud → Safari na iPhonie.
- Wzmocnione wykluczanie plikow kluczy, lokalnych baz i danych z GitHub (`.gitignore`).
- Wszystkie istniejace obliczenia i moduly v6.2 pozostaja bez zmian.
- Potwierdzony sklad Philadelphia 76ers 2026/27 nalezy pobierac z danych sezonowych; nie wpisywac statycznego zakazu dla LeBrona Jamesa lub Jaylena Browna.

**Uwaga:** sama aktualizacja NIE publikuje strony. Wdrozenie na Streamlit Cloud jest osobnym krokiem, opisanym w `PUBLIKACJA_NA_TELEFON.md`.

# BestBets — NBA Intelligence v6.2

Aktualizacja do działającej u Ciebie wersji BestBets 6.1 na Windows 11. **Bez automatycznego stawiania zakładów, bez obietnic wygranych.**

## Zmiany względem 6.1

1. **Kontrola jakości prognoz zawodników**: przed wyświetleniem oferty sprawdza liczbę rozegranych meczów, status kontuzji, możliwą zmianę minut, historyczny błąd prognozy, godzinę meczu oraz świeżość kursu. Oceny: `WERYFIKUJ`, `OSTROŻNIE`, `WSTRZYMAJ`. To **ocena danych, nie rekomendacja obstawienia**.
2. **Realistyczniejsze oznaczenie ryzyka**: osobno pokazuje surową, *nieskalibrowaną* szansę modelu i wskaźnik z ostrożnościową korektą w kierunku 50%. Ta korekta to **heurystyka / test wrażliwości**, **nie kalibracja empiryczna**; sama z siebie nie poprawia rzeczywistej trafności.
3. **Walk-forward dla zawodnika**: przy rynku widać `MAE walk-forward` (średni bezwzględny błąd wcześniejszych prognoz) i liczbę sprawdzonych historycznych prognoz. Przy każdej prognozie wykorzystuje tylko wcześniejsze mecze.
4. **Czytelniejsza tabela kursów**: uwidocznione ostrzeżenia, ocena danych i filtry; domyślnie ukrywane mecze rozpoczęte/stare kursy. Można zwinąć skorelowane warianty do jednej linii na zawodnika/rynek/stronę, nie usuwa to nic z pliku CSV.
5. **Mój dodatkowy pomysł: automatyczne archiwum kursów**. Gdy BestBets pobierze aktualne realne oferty z The Odds API, zapisuje je (bez klucza API) do `data/historyczne_kursy.csv`, nie częściej niż raz na godzinę dla identycznego rynku i bukmachera. Aplikacja nie próbuje „dorobić” kursów z dawnych meczów.
6. **Automatyczny tryb historycznego backtestingu na tym archiwum**. Po zakończeniu meczu zestawia ofertę sprzed meczu ze statystykami zawodnika. Zachowuje wyłącznie pary OVER/UNDER od jednego bukmachera dla dokładnie tej samej linii, dobiera jeden reprezentatywny rynek na zawodnika/mecz/statystykę (zapobiega sztucznemu zawyżaniu próby 20 kursami tej samej pozycji) i sprawdza zgodność drużyn. Gdy brak danych, informuje o tym. **Nie ma wiarygodnego historycznego ROI dopóki archiwum nie obejmie wielu zakończonych gier.**
7. Zachowane: **5 000 symulacji na mecz, widok szczegółów, lokalne oznaczenia drużyn i automatyczne loga, injury report, NBA Data Lab, terminarz, porównywarka The Odds API, kalkulator kursów, statystyki i dotychczasowy backtesting**.

## Instalacja poprawki w Twoim folderze

1. Zamknij czarne okno serwera BestBets (`START_BESTBETS.bat`).
2. Rozpakuj `BestBets_v6_2_POPRAWKA.zip`.
3. Wejdź do rozpakowanego folderu **bestbets-v6.2-poprawka** i skopiuj **jego zawartość**, nie folder w całości.
4. Wklej pliki do `Pulpit\BestBets_NBA_v4` w miejscu, gdzie znajdują się `app.py` i `START_BESTBETS.bat`. Potwierdź zastąpienie plików.
5. **Zachowaj** `.venv`, `.streamlit`, `data`, `assets`; szczególnie **nie usuwaj `.streamlit/secrets.toml`**. Twój klucz The Odds API nie znajduje się w paczce.
6. Kliknij `START_BESTBETS.bat`. Wejdź na `http://localhost:8501`.
7. Wybierz zakładkę **Kursy i value → Model value graczy**. Zobaczysz nowe oceny danych i filtry. W **Backtesting** pojawi się opcja **Automatycznie zapisane kursy**.

## Jak działa archiwizacja?

- Musisz **pozostawić aplikację uruchomioną** i regularnie otwierać zakładkę kursów, aby aktualizacje się zbierały. Streamlit odświeża panel w trakcie aktywnej sesji; nie jest to usługa działająca w tle, gdy komputer lub proces są wyłączone.
- Archiwum pojawia się w `data/historyczne_kursy.csv`. Plik nie zawiera klucza API. W **pełnej wersji** lub na publicznym darmowym hostingu lokalne dane mogą zniknąć przy restarcie serwera — do długotrwałego archiwizowania potrzebna będzie zewnętrzna trwała baza.
- Nie archiwizujemy ofert z oznaczonym jako nieaktualny feedem, kursów po rozpoczęciu meczu ani bez prawidłowej ceny.
- Statystyki z NBA Stats i ceny z The Odds API pozostają zależne od dostępności źródeł i limitów dostawcy. `Betclic FR` nie jest `Betclic Polska`. Podawane ceny mogą nie być możliwe do zawarcia na polskich kontach.
- Przed podjęciem jakiejkolwiek decyzji sprawdź faktyczny status zawodnika, datę i rynek. Model nie jest dostatecznie sprawdzony, aby traktować dodatnie EV jako dowód zyskowności.

## Testy programistyczne

`py -3.12 -m pytest -q tests`

Testy funkcji i importowania kodu nie zastępują end-to-end sprawdzenia na żywo z API i w przeglądarce. Bez weryfikacji w działającej aplikacji nie deklarujemy, że cały system jest produkcyjny.
