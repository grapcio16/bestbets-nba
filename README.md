# BestBets v7.21 — sezonowa analiza screenshotów + naprawa przełącznika modelu (10.11.2026)

## Import screenshotów jest odtąd analizą sezonową, a nie tylko OCR

`Kursy i value → Kalkulator → 📷 Import screenshot`:

- Po weryfikacji OCR wybierz **lokalny dzień rozpoczęcia meczów** z fotografii; aplikacja dopasowuje każdego zawodnika przez pełną nazwę i (jeśli dostępny) stabilny **ESPN Player ID** do aktualnych składów.
- Na żądanie pobiera **sezonowy gamelog każdego rozpoznanego zawodnika**, nie tylko 10–12 ostatnich spotkań z szybkiego fallbacku. Gdy API ESPN odmawia udostępnienia pełnego gamelogu, próbuje dopasować dane dostępne w NBA Stats/CDN/ESPN, ale **oznacza je jako próbkę częściową**. Niczego nie uzupełnia fikcyjnymi wynikami.
- Liczy **dokładnie** Over, Under i ewentualny Push w **wszystkich pobranych występach od 1 października bieżącego sezonu** i ostatnich 10 występach na **konkretnej linii** ze screena, wraz z liczbą rozegranych meczów i średnią. Występy DNP nie są liczone jako 0. Brak kursu nie blokuje statystyk.
- Po wybraniu dnia dopasowuje konkretny przyszły mecz drużyny z terminarza. Jeśli nie da się jednoznacznie ustalić przeciwnika, **nie zgaduje**.
- Z rzeczywistych finałów ESPN **wyłącznie sprzed meczu** liczy średnią punktów traconych przez CAŁĄ drużynę rywala od początku sezonu oraz w ostatnich 10. Wariant badawczy `Prediction Engine 2.0` stosuje ostrożną, maks. 8% korektę tempa punktowego gracza dla PTS/PRA. Ta korekta **NIE** jest pomiarem obrony pozycji, wpływu kontuzji ani gwarancją trafności. Korekty dla REB, AST i 3PM wymagają innych, rzeczywistych danych.
- Wyniki są rozdzielone na **historyczny procent występów Over/Under** i **niekalibrowane prawdopodobieństwo kolejnego meczu**, z osobnymi kolumnami, ostrzeżeniami o danych, tabelą defensywy rywali, wykresem wyników zawodnika i CSV. Użytkownik sam wybiera rynek i kierunek; aplikacja nie generuje pewnych rekomendacji.
- Zrzut jest przetwarzany lokalnie przez Tesseract w sesji Streamlit; nie przechowujemy screena na serwerze ani nie publikujemy go w repozytorium. Pytania o komercyjne prawa do źródeł danych należy rozstrzygnąć przed premierą PRO.

## Dlaczego eksperymentalny model nie zmieniał symulacji?

Gdy działały oficjalne NBA Advanced, oba modele korzystały z **identycznych średnich Pace, OFF/DEF** — przełącznik zmieniał etykietę, ale nie liczby. W v7.21 **wariant badawczy** przy minimum 4 zakończonych meczach każdej drużyny łączy **70% dotychczasowej prognozy NBA Advanced i 30% ważonej formy z ESPN**, z korektą siły rywali i regresją do średniej.

- **Model podstawowy v7.2 i jego 5000 przebiegów pozostają NIEZMIENIONE**.
- Każda karta pokazuje nazwę faktycznie użytego źródła modelu, a zakładka Symulacje zawiera porównanie obu wariantów i różnice punktów/procentów.
- Jeśli brak historii pozwalającej na korektę, warianty mogą być identyczne: wyświetlamy jawną informację zamiast wymyślać różnicę.
- **Nie ma jeszcze dowodu**, że badawcza mieszanka zwiększa trafność. Wymaga osobnego chronologicznego walk-forward i kalibracji.

Testy `test_season_props_v721.py` chronią pełno-sezonowe wyniki, granice daty, statusy odrzuconych zawodników, obronę rywala i realne działanie przełącznika. Nie podnosimy procentów sztucznie — poprawiamy wejścia i transparentność.

---

# BestBets v7.20 — automatyczny Performance Tracker (10.11.2026)

Najważniejsza zmiana: **rozliczanie zapisanych prognoz nie wymaga już ręcznego kliknięcia przycisku**.

### Automatycznie podczas wizyty
- Otworzenie zakładki `Performance Tracker` sprawdza lokalną lub zewnętrzną bazę: jeśli są **rozpoczęte i nierozliczone** spotkania, pobiera historię wyników ESPN i rozlicza wszystkie mecze z finalnym statusem.
- Automatyczne sprawdzenie jest ograniczone do raz na **30 minut na sesję**; gdy brak oczekujących prognoz, nie wykonuje niepotrzebnych zapytań do ESPN.
- Widać czas ostatniego sprawdzenia, liczbę rozliczonych prognoz lub problem z danymi. Nadal istnieje ręczny przycisk ponownej weryfikacji.
- Odrzucamy częściowe i nieaktualne dane ESPN zamiast na ich podstawie zamykać zakłady. Zamrożonych prognoz nie zmieniamy, a finalne wyniki rozliczamy wyłącznie raz.

### Bez otwierania BestBets — GitHub Actions
- `.github/workflows/tracker-auto.yml` uruchamia `tracker_automation.py` o **07:25, 12:25, 18:25 i 23:25 UTC** (harmonogram GitHub jest *best effort*, może się opóźnić; możliwy też ręczny `workflow_dispatch`).
- Worker używa wyłącznie aktualnych danych ESPN, zapisuje pregame prognozy dla spotkań do **36 godzin naprzód**, z minimum 15 minut przed początkiem meczu, a następnie rozlicza zakończone spotkania.
- Zapisuje osobno `auto_legacy_v72` i `auto_research_form_v74`. **Nie nadpisuje** ręcznych prognoz `legacy_v72` i `research_form_v74`, bo runner może mieć inne dostępne dane NBA Advanced niż aktywny Streamlit.
- Algorytmy symulacji nie są zmienione; standardowa kalkulacja nadal wykonuje **5000 losowań** na mecz.
- Nie wymyśla prognoz dla meczu bez minimum zakończonych spotkań i nie odtwarza nieznanych przedmeczowych wartości po zakończeniu spotkania.

### Konfiguracja konieczna do działania bez wizyt użytkownika

1. Utwórz własną **trwałą bazę PostgreSQL** (zewnętrzny dostawca).
2. W ustawieniach aplikacji **Streamlit Cloud → Settings → Secrets** dodaj `TRACKER_DATABASE_URL = "postgresql://..."`.
3. W repozytorium **GitHub → Settings → Secrets and variables → Actions → New repository secret** dodaj `TRACKER_DATABASE_URL` z **tym samym** URL. Nie zapisuj haseł w repozytorium ani screenshotach.
4. Otwórz **GitHub → Actions → BestBets — automatic pregame tracking and results → Run workflow** i zweryfikuj `success`. Pierwszy uruchomiony cykl może zapisać 0 prognoz, jeśli nie ma jeszcze odpowiedniej historii lub zaplanowanych meczów.
5. Na stronie Performance Tracker wybierz właściwy wariant `auto_...` i sprawdź daty zamrożonych prognoz. Trwałość zależy od poprawnej konfiguracji zewnętrznej bazy.

**Bez `TRACKER_DATABASE_URL` na GitHub Actions zadanie harmonogramu zgłosi błąd i NIE będzie autonomicznie zapisywało danych.** Lokalne SQLite działa podczas wizyty, ale dane mogą zniknąć po restarcie Streamlit. Dopóki ustawienia bazy nie są potwierdzone, nie należy obiecywać automatyzacji 24/7.

### Ograniczenia i następne testy
- Rozliczanie dotyczy **prognoz modelu NBA (zwycięzca, suma i punkty drużyn)**. Nie ma jeszcze automatycznego dopasowania i rozliczenia prywatnych kuponów Betclic, kursów i Player Props. Wprowadzanie kuponów wymaga osobnego źródła danych, identyfikacji rynku i czasu zakupu.
- Prognozy `auto_*` używają bieżących wyników ESPN, nie tworzą domniemanych statystyk o kontuzjach ani alternatywnych danych Advanced.
- Brak dowodów na lepszą skuteczność wyników: automatyzacja polepsza jakość zbierania danych, nie trafność modelu.
- Testy `test_tracker_v720.py` sprawdzają izolację wariantów, zapis raz przed tipoff, idempotencję rozliczeń, odrzucanie wyników przyszłych i brak cichego fallback SQLite w trybie harmonogramu.

---

# BestBets v7.19 — symulacje: własne linie, ryzyko i wrażliwość prognoz (9.11.2026)

Ulepszono `Symulacje 5000 → Szczegóły meczu → 🎯 Linie i wrażliwość`. Aktualizacja **nie zmienia średnich wyników, losowania, liczby przebiegów 5000 ani domyślnego modelu**. Wszystkie procenty są częstościami wystąpienia zdarzeń pod ZAŁOŻENIAMI bieżącego modelu — nie są skalibrowanymi szansami.

- Użytkownik wpisuje własną linię sumy meczu `Over/Under` lub handicap gospodarzy ze znakiem, np. `−6,5`; brak automatycznie wymyślanych kursów.
- Te same **5000** losowań co na karcie meczu jest sprawdzane względem podanej linii. Wyświetlane osobno procenty obu stron oraz zwrot (push) dla całkowitych linii. Wyrównanie matematyczne: obie strony + zwrot = 100%.
- Opcjonalnie użytkownik wpisuje rzeczywiste kursy z własnej oferty. Aplikacja oblicza próg rentowności i **wyłącznie niekalibrowane modelowe EV**. Kurs jest ręczny i nie jest potwierdzony w czasie rzeczywistym.
- Rozkład: 10.–90. percentyl wyników / przewagi punktowej. Wąski błąd próbkowania Monte Carlo NIE zastępuje szerokiej niepewności modelowej.
- **Badawczy test wrażliwości** uruchamiany dopiero po kliknięciu porównuje obecny model z dostępnymi wariantami `legacy`, `recency`, `opponent-adjusted ridge`, `venue`. Używa tylko prawdziwych wyników sprzed terminu analizowanego meczu. Nie są to niezależne ani skalibrowane prognozy, a rozbieżność między nimi nie jest przedziałem ufności.
- **Zapis CSV**: ID meczu, data/UTC utworzenia, termin rozpoczęcia, model, linia, prawdopodobieństwa, opcjonalny ręczny kurs i modelowe EV. Flaga `pregame` wyraźnie oznacza zapisy po rozpoczęciu meczu; nie można ich przedstawiać jako wcześniejszych prognoz. Dane nie są przechowywane w backendzie kuponów ani wysyłane do bukmachera.
- Testy `test_simulation_lines_v719.py` oraz pozostała automatyczna regresja CI zabezpieczają rozliczanie integer push, handicap minus/plus, dokładnie 5000 losowań i brak wykorzystania wyników przyszłych spotkań.

**Dlaczego to ważne:** po dzisiejszej nocy możemy porównać nie tylko trafienie zwycięzcy, ale także odchylenie od dokładnie obstawionych linii. Żaden wynik EV nie oznacza potwierdzonej opłacalności. Przed komercjalizacją nadal potrzebujemy historii rzeczywistych kursów i niezależnej kalibracji.

---

# BestBets v7.18 — Prediction Engine 2.0 (wariant badawczy, 9.11.2026)

Dodano **kandydacki** model Player Props i rygorystyczne porównanie ze starym silnikiem. **Żaden z modeli nie jest kalibrowany; nie wdrażamy automatycznych typów ani nie obiecujemy lepszego ROI.** Podstawowy algorytm 5000 symulacji meczowych, terminarz i darmowe informacje NBA pozostają niezmienione.

## Jak działa v2

- **Minuty:** ważona średnia ostatnich 5, 10 i wcześniejszych meczów tej samej drużyny, z osobną symulacją zmienności minut, zakres 3–48.
- **Produkcja per minute:** ważone historyczne punkty, zbiórki lub asysty na minutę z losowaniem indeksów wcześniejszych meczów i mieszanką Poissona. **PRA** sumuje składowe z tym samym wylosowanym poprzednim meczem, częściowo zachowując ich współzależność.
- **Trójki:** kiedy rzeczywiste `FG3A` są dostępne, symuluje liczbę prób za trzy na minutę i skuteczność z łagodnym priorem Beta-Binomial. W przeciwnym razie stosuje wariant historyczny per-minute + Poisson.
- **Minimum 10 występów** odpowiedniej drużyny; nie dorabiamy zawodnikom danych bez logów, nie przenosimy automatycznie historii nowego klubu ze starego. Każda prognoza jest deterministyczna dla tej samej historii i daty.
- Dane **tylko sprzed meczu**, bez look-ahead; nie wykorzystujemy niepotwierdzonych absencji jako mnożnika. Prawdopodobieństwa z 2048 losowań są **NIEKALIBROWANE**.

## Gdzie zobaczyć

- `Kursy i value → Kalkulator → Import screenshot`: dla każdej zweryfikowanej pozycji wyświetlamy obok siebie obecny model i `P(OVER) v2` z prognozą oraz minutami v2. Brak danych oznacza wstrzymanie, nie sztuczne procenty.
- `Kursy i value → Kalkulator pojedynczego zawodnika`: po wyliczeniu szczegóły kandydata v2 pojawiają się obok standardowej analizy, gdy jest minimum 10 rzeczywistych występów.
- `Backtesting → Prediction Engine 2.0 — Model Battle`: **dopiero po kliknięciu** pobieramy wybrane sezony (2024/25, 2025/26, 2026/27; pełna historia zależy od NBA Stats), liczymy przewidywania dla rzeczywistych spotkań zawodników w porządku chronologicznym, z tym samym zbiorze dla obu modeli. Widoczne: MAE, Brier, log loss, trafność Over/Under, bias, okres późniejszych 30% i eksport CSV.
- Testowane **linie są syntetyczne**: `floor(średnia z poprzednich 10) + 0.5`, nie są kursami bukmacherów. Taki test NIE udowadnia dodatniego ROI. Rok/sezon i klub są oddzielane przy trenowaniu, co zapobiega mieszaniu zawodników sprzed transferów oraz przyszłych meczów.

## Co jeszcze jest potrzebne przed PRO

Zbieranie rzeczywistych, oznaczonych czasem linii i kursów przed meczami, potwierdzenie źródeł danych o kontuzjach i rotacji, niezależne daty walidacji, kalibracja dla osobnych rynków oraz kontrola licencji na komercyjne wykorzystanie danych.

Testy: `test_prediction_v718.py`, dotychczasowy `test_screen_v717.py` i pozostały CI. Nowy silnik to kandydat, który może okazać się gorszy — wyniki muszą zdecydować, czy w przyszłości go zastosujemy.

---

# BestBets v7.17 — screenshot importer BETA (9.11.2026)

**Nowe:** `Kursy i value → Kalkulator → Import screenshot — analiza wielu pozycji`. Jedno zdjęcie może pokazać wiele osobnych rynków punktowych; importer OCR rozpoznaje pola zawodnik / Over / Under / linia / kurs i wyświetla **edytowalną tabelę do obligatoryjnej weryfikacji przez użytkownika**. Wspieramy czytelne dwukolumnowe PL/EN listy oraz proste listy jednokolumnowe, a **nie wszystkie możliwe aplikacje bukmacherskie**.

- Lokalny OCR Tesseract: `pytesseract` w `requirements.txt`, `tesseract-ocr`, `tesseract-ocr-pol`, `tesseract-ocr-eng` w `packages.txt`. Zrzuty przetwarzane na serwerze po kliknięciu, bez wysyłania ich do zewnętrznych modeli AI i bez zapisywania na dysk ani w GitHub. Limit 8 MB / 12 MP i limit czasu OCR 18 s.
- **Nie zakładamy poprawności żadnych wyników OCR**: wszystkie wpisy trzeba sprawdzić; nierozpoznane kursy są puste. Użytkownik może poprawić i dodać wiersze przed jednorazowym batch wyliczeniem.
- Rynki: `PTS`, `REB`, `AST`, `FG3M`, `PRA`. Oddzielnie kurs na Over i Under, jeden gracz / linia / statystyka na wiersz.
- Wyniki: procenty Over/Under **niekalibrowanego modelu**, przedmeczowy próg wynikający z kursu, dwustronne prawdopodobieństwo bez marży (tylko jeśli są oba kursy), surowe predykcje, próba i hit-rate L10. Wstrzymane analizy są jawnie oznaczone.
- **Fail closed**: brak dokładnego nazwiska, niewystarczająca próbka 10 występów w aktualnym klubie, stare dane, niepełny kurs, brak rynku lub całkowita linia z możliwością zwrotu → bez procentowej prognozy. Aktualność oferty, skład i matchup nie są potwierdzone przez sam screenshot.
- Wyniki są informacją badawczą, **nie są rekomendacjami** ani dowodem uzyskania przewagi nad bukmacherem. Screenshot może ujawniać prywatne informacje: nie wgrywaj salda/numeru konta. Kontrola użytkownika jest obowiązkowa.
- Algorytm 5000 symulacji i stary kalkulator pojedynczego zawodnika **nie są zmieniane**. Nowy tryb jest niezależny; oddzielna praca nad Prediction Engine 2.0 i niezależnym walk-forward jest następna.
- Testy `test_screen_v717.py` używają wyłącznie syntetycznych tokenów OCR; zdjęcia użytkownika nie są publikowane w repozytorium.

---

# BestBets v7.16 — Rotation Intelligence (9.11.2026)

Dane rotacji i kontuzji w szczegółach pojedynczego meczu, **bez zmiany wyniku 5000 symulacji**.

- Nowy widok **Symulacje 5000 → Szczegóły meczu → „Rotacja i absencje”**: oddzielnie dla każdej drużyny zobaczysz liczbę zawodników z projekcją minut, statusy ESPN oraz liczbę minut historycznej projekcji przypisanych do graczy oznaczonych Out/Doubtful i Questionable/Day-to-day.
- **Trend minut 3 vs 7 ostatnich występów** z rzeczywistych box score, z rozróżnieniem „Więcej minut”, „Mniej minut”, „Stabilnie” i „Za mała próba”. Tylko spotkania sprzed analizowanego meczu, bez fałszywych DNP=0.
- Pokazujemy także **zawodników zgłoszonych jako kontuzjowani bez dostępnych projekcji**, nie tworząc dla nich wymyślonych wartości. Rozpoznawanie łączy pełną znormalizowaną nazwę i drużynę; pozycja tylko z katalogu ESPN bieżącego klubu.
- Statusy ESPN są orientacyjne, **nie potwierdzają aktywnego składu**; brak statusu nie znaczy, że zawodnik jest zdrowy. Przy danych oznaczonych jako stale/niepełne podsumowanie minut ryzyka jest ukryte i wyświetlany jest alert.
- Projektowana suma minut zawodników nie jest równa 240 i nie wolno jej używać do automatycznego odejmowania punktów drużynie. Korekta wyniku na podstawie statusów wymaga pregame snapshotów i walidacji wpływu absencji na historycznych spotkaniach.
- Nie zmieniliśmy żadnej prognozy zwycięzcy, sumy punktów, kursów ani algorytmu. Dane odświeżają się tylko przy otwarciu szczegółów, aby nie przeciążać Streamlit Cloud.
- Testy jednostkowe `test_rotation_v716.py` oraz dotychczasowe testy regresyjne są uruchamiane w GitHub Actions.

---

# BestBets v7.15 — audyt jakości danych i nowe funkcje badawcze (9.11.2026)

Najważniejszy wniosek audytu: **domyślne 5000 symulacji korzysta z prostego modelu średnich punktowych** — do 12 ostatnich zakończonych meczów obu drużyn lub, jeśli dostępne w świeżym cache, NBA Advanced Pace/OFF/DEF. Dzisiejsze składy, kontuzje, minuty, odpoczynek i H2H **nie korygują automatycznie wyniku drużyn**. Historia ESPN obejmowała maksymalnie trzy ostatnie miesiące sezonu; dane NBA Advanced z stats.nba.com często są niedostępne w chmurze.

**Nowe funkcje (bez zmiany produkcyjnego modelu):**

- W zakładce Symulacje → „Głębsze dane — ustawienia badawcze” opcjonalna historia **do 6 miesięcy** bieżącego sezonu; domyślnie wciąż 3, na początku listopada dostępne są tylko rzeczywiste mecze od startu sezonu, nie łączymy sezonów.
- Przycisk ręcznego pobrania aktualnych **NBA Advanced** (Pace, OFF/DEF Rating) z zachowaniem fallback ESPN i jawnych ostrzeżeń, jeśli Stats jest blokowane. Bez dodatkowych żądań przy zwykłym przeglądaniu kart.
- W szczegółach meczu rozwijany **audyt jakości danych**: próby 5/10/20, punkty zdobyte i stracone, margines, odchylenie sumy, splity dom/wyjazd, przerwa/back-to-back, prawdziwe Pace/OFF/DEF jeśli dostępne. Każdy wynik liczymy tylko na meczach zakończonych PRZED analizowanym spotkaniem (brak look-ahead).
- **Badawczy model venue**: 25% historycznej korekty dom/wyjazd, ograniczonej do ±3 punktów i minimum 4 meczów odpowiedniego typu dla obu drużyn; widoczny wyłącznie jako hipoteza. W osobnym chronologicznym holdoucie pojawia się jako `venue_research`; nigdy nie zastępuje domyślnego modelu bez testów na niezależnych danych.
- Testy `test_simulation_data_audit.py` w CI sprawdzają brak przecieku przyszłych spotkań, minimalne próby, oficjalne dane Advanced i niewrażliwość hipotezy na wyniki przyszłych meczów.

Rozszerzenie danych **nie stanowi dowodu poprawy prognoz**. Nadal potrzebne: pregame injury report, potwierdzona rotacja, zweryfikowane minute projections i niezależna kalibracja, przed używaniem tych czynników jako modyfikatorów wyniku.

---

# BestBets v7.13 — poprawka TOP10: kompletne dane i zwarty układ

- Naprawa po v7.12: wymuszona nowa wersja cache Streamlit dla rankingu. Stare wyniki zapisane przed dodaniem kolumn minut, przeciwnika i pozycji nie będą już wyświetlane jako aktualne.
- Karta TOP10: **mecz goście @ gospodarze** w prawym górnym rogu, **nominalna pozycja ESPN obok nazwiska**, a **punkty, zbiórki, asysty oraz rzeczywiste minuty MM:SS w jednym rzędzie**.
- Rzeczywisty mecz ustalamy z terminarza po ID ESPN, a minuty z ukończonego box score. Dla brakujących pozycji można posłużyć się osobno pobranym składem ESPN **tego samego klubu i identyfikatorem zawodnika**. Nie wolno wnioskować pozycji ze statystyk.
- Braki w danych nadal są oznaczane **—**. Automatyczne pobranie składu jest zależne od dostępności ESPN.
- Kontynuacja projektu bez zmian w modelu symulacji, Injury Report ani terminarzu. Testy: `test_center_v713.py`.

---

# BestBets v7.12 — minuty, przeciwnik i pozycja w TOP 10 (8.11.2026)

- W **Centrum → TOP 10** każda karta zawodnika pokazuje teraz **czas gry (MM:SS), przeciwnika (skrót drużyny)** oraz **pozycję (PG/SG/SF/PF/C, jeśli podało ją ESPN)**, oprócz punktów, zbiórek i asyst.
- Dane pochodzą z **rzeczywistych box score zakończonych spotkań ESPN**. Pozycja jest nominalnym oznaczeniem z raportu, a nie automatycznie ustaloną rolą zawodnika w każdym ustawieniu.
- Brak potwierdzonych minut lub pozycji wyświetlamy jako **—**, nigdy jako zero czy wynik wywnioskowany ze statystyk.
- Przeciwnika ustalamy z rzeczywistego meczu po identyfikatorze ESPN i aktualnej drużynie zawodnika; godziny i granice poprzedniego dnia pozostają lokalne dla użytkownika.
- Nie zmieniono rankingu, symulacji, Injury Report ani terminarza. Regression tests: `test_center_v712.py`.

---

# BestBets v7.11 — uporządkowane Centrum (8.11.2026)

- Usunięto wyłącznie cztery **informacyjne** kafelki spod nagłówka Panel główny (Terminarz / Sezon / Rynki zawodników / Kursy); źródła danych oraz obliczenia pozostają bez zmian.
- **Terminarz dnia w Centrum pozostaje**: karty drużyn, rzeczywiste wyniki, wybór daty i nawigacja dniami bez prognoz symulacji.
- **Injury Report pozostaje**.
- Ranking TOP 10 zawodników z poprzedniego dnia ma teraz dwukolumnowy, responsywny układ kart: pozycja, klub/logo oraz duże i czytelne PTS/REB/AST. Źródłem nadal są wyłącznie rzeczywiste box score zakończonych spotkań ESPN.
- Zachowano oddzielne zakładki Terminarz i Symulacje 5000; algorytmy, kursy i modele **nie uległy zmianie**.

---

# BestBets v7.10 — karty terminarza i nawigacja po datach (8.11.2026)

- **Centrum:** zamiast tabeli dzisiejszych meczów pokazujemy karty z herbami, nazwami drużyn, lokalną godziną i statusem. Dla zakończonych spotkań można zobaczyć **wyłącznie rzeczywisty wynik** z feedu ESPN/NBA; nie pokazujemy prognoz ani rezultatów symulacji.
- **Nawigacja:** ◀ poprzedni dzień, ▶ następny dzień, „Dzisiaj” oraz kalendarz do wyboru konkretnej daty. Wybrana data współdzielona między Centrum i Terminarzem w ramach sesji.
- **Terminarz:** taki sam widok kartowy jako domyślny, opcjonalna tabela, filtr statusu i eksport CSV dla aktualnie wybranego dnia.
- **Daty globalne:** filtrowanie według lokalnego dnia w strefie użytkownika (również przez granice UTC i DST). Przy cofaniu o wcześniejsze miesiące pobieramy tylko niezbędne archiwa miesięczne ESPN; brak danych jest jawnie komunikowany.
- **Bez zmian** w algorytmie 5000 symulacji ani module wyznaczania predykcji.
- **Testy:** `test_schedule_v710.py` oraz kontrola interakcji Streamlit w GitHub Actions.

---

# BestBets — v7.9: globalny interfejs NBA (8 listopada 2026)

Ta aktualizacja dotyczy **interfejsu, czasu i prezentacji danych**. Algorytm symulacji oraz 5000 przebiegów na mecz pozostają **bez zmian**.

- Publiczna zakładka „Telefon i publikacja” usunięta; konfiguracja GitHub, Streamlit i API Secrets w [dokumentacji technicznej](docs/PUBLIKACJA_TECHNICZNA.md).
- Automatyczna strefa czasowa z `st.context.timezone`, ręczny wybór pełnej bazy IANA, konwersja UTC i DST w Centrum, Terminarzu, Symulacjach i Performance Trackerze.
- Centrum pokazuje mecze **bieżącej lokalnej daty**, logotypy drużyn, TOP 10 zawodników **poprzedniego lokalnego dnia** według rzeczywistych box score ESPN; w razie niepełnych danych pojawia się ostrzeżenie.
- Injury report: drużyny oznaczone kodem i logo; aliasy ESPN poprawione; nierozpoznanych klubów nie zgadujemy.
- Nowa kolorystyka i zatwierdzona ikona BestBets; osobny plik SVG pozostaje do skalowania w przyszłych materiałach.
- [Audyt siedmiu prognoz v7.7 z 7.11.2026](docs/AUDYT_NBA_2026-11-07.md): 3/7 zwycięzców, MAE sumy 18,89 pkt. Model eksperymentalny **nie zastępuje** podstawowego bez rzetelnej walidacji.
- [Testy regresyjne](test_nov8.py) obejmują DST, daty lokalne, ranking i injury report.

---

## Historia starszych wersji

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
