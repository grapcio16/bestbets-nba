# BestBets — dokumentacja techniczna publikacji

## GitHub
Kod aplikacji przechowuj w repozytorium GitHub. Nie publikuj lokalnych plików secrets.toml, plików .env, haseł ani baz z danymi prywatnymi. Przed wysłaniem sprawdź zawartość zmian.

## Streamlit Community Cloud
Połącz repozytorium, wybierz gałąź main i plik startowy app.py. Skonfiguruj zgodną wersję Pythona oraz zależności z requirements.txt.

## API Secrets
W panelu Streamlit Cloud przejdź do App settings → Secrets i ustaw:

```toml
ODDS_API_KEY = "WPROWADZ_W_PANELU_SECRETS"
```

Nie wpisuj rzeczywistego klucza do kodu ani dokumentacji. W razie ujawnienia klucza natychmiast go unieważnij.

## Telefon
Otwórz adres aplikacji w Safari → Udostępnij → Dodaj do ekranu początkowego. To skrót do strony, nie aplikacja natywna.

## Ograniczenia
Wspólne limity API, nietrwała lokalna pamięć na darmowym hostingu oraz eksperymentalne prognozy wymagają osobnego monitorowania. Do trwałej historii Performance Tracker skonfiguruj zewnętrzną bazę przez TRACKER_DATABASE_URL w Secrets.
