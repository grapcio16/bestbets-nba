# HOOPZARO — 7 dni porównania BALLDONTLIE z ESPN

Status: **przygotowany tryb testowy, brak migracji produkcyjnej**.

## Co testujemy

- Skończone mecze identyfikowane po *parze drużyn* i dniu, ponieważ identyfikatory ESPN i BALLDONTLIE są różne.
- Pozytywne występy zawodników: PTS, REB, AST, FG3M, FG3A, FGA, OREB, DREB, TOV.
- Rozbieżności w minutach powyżej 1 minuty (BDL może zaokrąglać minuty).
- Brakujące występy, niezgodności wyniku, brakujące pola i błędy API.
- Wyłącznie dane z zakończonych meczów; brakujące wartości nie są dopisywane jako zera.

**Nie** nadpisujemy `Neon`, nie zmieniamy trackera, symulacji, publicznego interfejsu ani danych wejściowych modeli.

## Przygotowanie konta

1. Na https://www.balldontlie.io/ utwórz konto i zapoznaj się z planem GOAT dla NBA.
2. Dokumentacja: https://docs.balldontlie.io/ — podczas 7-dniowego triala GOAT obowiązuje **5 requestów/min**, konieczna jest metoda płatności; po okresie próbnym następuje płatna konwersja, jeśli trial nie zostanie anulowany.
3. Dodaj sekret o nazwie `BALLDONTLIE_API_KEY` tylko w miejscu wykonywania audytu. Nie wklejaj klucza do czatu, README, plików repozytorium ani pliku `streamlit/secrets.toml` przeznaczonego do commita.

## Test lokalny

Uruchom w izolowanym środowisku z `requests` i `pandas` (już są w wymaganiach aplikacji):

```powershell
$secureKey = Read-Host "BALLDONTLIE API key" -AsSecureString
$env:BALLDONTLIE_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
python -m unittest -v test_bdl_shadow_audit.py
python bdl_shadow_audit.py --date 2026-11-17 --max-games 10
Remove-Item Env:BALLDONTLIE_API_KEY
Remove-Variable secureKey
```

Wynik powstanie w `.bdl-audit/bdl-shadow-2026-11-17.json` (katalog ignorowany przez Git).

## Test w GitHub Actions

Plik `.github/workflows/bdl-shadow-audit.yml` udostępnia **ręczne** uruchomienie i pobranie raportu jako artifact po dodaniu sekretu w GitHub `Settings → Secrets and variables → Actions`.

**Nie uruchamia się automatycznie** i nie działa na `main`, dopóki użytkownik nie zatwierdzi PR z tą gałęzią. Nie dodajemy harmonogramu ani nie aktywujemy płatnego triala bez osobnego potwierdzenia właściciela.

## Kryteria oceny po siedmiu dniach

- Docelowo minimum **99% zgodnych porównywalnych wartości** podstawowych statystyk (cel, nie wynik pomiaru).
- Różnice minut, niekompletni zawodnicy, brak statystyk trójek i niezgodne wyniki wymagają ręcznego zbadania.
- Przed migracją sprawdzamy osobno aktualność kontuzji, historię L5/L10/L15, oceny zaawansowane i wpływ na skuteczność modeli. **Ten pierwszy audyt nie pokrywa jeszcze tych źródeł.**
- Warunek prawny: uzyskanie pisemnego wyjaśnienia od BALLDONTLIE co do pochodzenia danych i praw osób trzecich. Abonament API nie daje automatycznie prawa do zdjęć zawodników i logo drużyn.

Repozytorium pozostaje bezpieczne: wszystkie zmiany są w osobnej gałęzi, bez ingerencji w publiczną aplikację.
