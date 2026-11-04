# BestBets v6.3 — publikacja w internecie i uruchomienie na iPhonie

## 1. Lokalnie (Twój obecny Windows 11)

1. Wgraj poprawkę v6.3 do istniejącego `Pulpit\BestBets_NBA_v4`.
2. Zachowaj `.venv`, `.streamlit/secrets.toml` oraz folder `data`.
3. Uruchom `START_BESTBETS.bat` i otwórz `http://localhost:8501`.
4. W menu wybierz **Telefon i publikacja**.

## 2. Przed publikacją — kontrola prywatności

- **NIE** publikuj `.streamlit/secrets.toml`, żadnego lokalnego klucza API ani zrzutów ekranu z kluczem.
- Nie przesyłaj `.venv`, `__pycache__`, `data` (kursy i cache), `*.json` z cache ani plików tymczasowych.
- **Najbezpieczniej: rozpakuj oddzielną paczkę `BestBets_v6_3_GITHUB.zip` i prześlij tylko jej zawartość.** Zawiera potrzebne pliki źródłowe, `requirements.txt`, `.streamlit/config.toml` i `assets/`.
- W repozytorium powinien być `.gitignore`. **Uwaga:** przy ręcznym przesyłaniu plików w przeglądarce GitHuba reguły `.gitignore` mogą NIE być stosowane; nie wybieraj lokalnych prywatnych plików.
- Jeśli klucz był kiedyś pokazany publicznie, unieważnij go przed użyciem w publicznej aplikacji.

## 3. GitHub

1. Zaloguj się na https://github.com/ .
2. Utwórz repozytorium np. `bestbets-nba` (na początek prywatne, jeśli chcesz najpierw sprawdzić zawartość; potem sprawdź uprawnienia hostingu).
3. Rozpakuj `BestBets_v6_3_GITHUB.zip` i prześlij **zawartość** jego folderu `bestbets-nba`; zachowaj strukturę podfolderów (`.streamlit/`, `assets/`).
4. Sprawdź na GitHubie, czy plik `.streamlit/secrets.toml` NIE występuje w repozytorium.

## 4. Streamlit Community Cloud

1. Otwórz https://share.streamlit.io/ i zaloguj się przez GitHub.
2. **Create app** → wskaż repozytorium `bestbets-nba`, gałąź `main`, plik startowy `app.py`.
3. W ustawieniach zaawansowanych wybierz **Python 3.12** (jeśli dostępny).
4. W polu **Secrets** ustaw prywatnie:

   ```toml
   ODDS_API_KEY = "TWOJ_NOWY_KLUCZ_Z_PANELU_DOSTAWCY"
   ```

5. Zapisz ustawienia i uruchom wdrożenie. Po uzyskaniu adresu `https://...streamlit.app` sprawdź terminarz, statystyki, symulacje i źródła kursów.
6. Nigdy nie wklejaj rzeczywistego klucza do repozytorium, czatu ani do plików publicznych.

## 5. Na iPhonie

Safari → otwórz PUBLICZNY adres `https://...streamlit.app` → Udostępnij → Dodaj do ekranu początkowego → ewentualnie Otwórz jako aplikację internetową → Dodaj. Nazwij skrót **BestBets**.

W ten sposób dodajesz skrót strony, **nie** natywną aplikację App Store. Ikona może zależeć od możliwości Safari i Streamlit.

## 6. Ograniczenia publicznego hostingu

- The Odds API ma **wspólny limit dla wszystkich odwiedzających**. Nie ma osobnego klucza na użytkownika. Obecny limit jest tylko zabezpieczeniem orientacyjnym; dla większego ruchu potrzebne są scentralizowane cache i limity żądań.
- Na darmowym hostingu pliki `data/` nie są trwałą bazą: archiwum kursów może zostać utracone przy restarcie. Do rzetelnego backtestingu potrzebna jest baza SQL lub zewnętrzne przechowywanie.
- NBA Stats i inne publiczne źródła mogą blokować połączenia z serwera chmurowego; nie gwarantujemy automatycznego dostępu.
- Betclic FR nie oznacza Betclic Polska. Modele są eksperymentalne i nie potwierdzają opłacalności zakładów.

## 7. Aktualizacje

Po wdrożeniu kolejne poprawki z lokalnego ZIP-a nie zaktualizują same publicznej strony. Należy zaktualizować repozytorium GitHub i zaczekać na ponowne wdrożenie Streamlit Cloud.
