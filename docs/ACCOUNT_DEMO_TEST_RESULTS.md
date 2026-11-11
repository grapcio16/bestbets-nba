# Wyniki demonstratora kont BestBets

Gałąź `feature/auth0-subscription-demo-20261112`, oparta na aktualnym `main`
(`2b8af03`) i kodzie PR #52 (`c37e7f1`). Publiczny interfejs pozostaje identyczny
z bazą. Nie wdrożono aplikacji, nie utworzono kont zewnętrznych i nie ma paywalla
na publicznym Streamlit.

| Walidacja lokalna | Wynik |
|---|---|
| Backend, adapter, sesje, OIDC i Playwright — SQLite | **115/115** |
| Ten sam zestaw — rzeczywisty PostgreSQL 17.11 | **115/115** |
| W tym scenariusze Playwright / Chromium 151 | **6/6** na każdej bazie |
| W tym nowe scenariusze bezpieczeństwa OIDC/sesji/konfiguracji | **25/25** na każdej bazie |
| Istniejące regresje projektu, unittest | **207/207** |
| Migracje od pustej bazy + Alembic schema check, obie bazy | OK |
| Publiczne źródła/HTML/CSS/assets/requirements.txt względem main | bez zmian |
| Kompilacja, whitespace i wzorce sekretów | OK |

Grupy pokrywają się; nie sumujemy tych liczb jako unikalnych testów.
Pierwsza próba unittest w samym virtualenv backendu nie miała zależności NBA/UI.
Po uruchomieniu w środowisku z zależnościami aplikacji wszystkie 207 testów przeszły.
Pozostały ostrzeżenia o przyszłych zmianach API httpx/Authlib/Starlette i pytest
zainstalowanych w środowisku; nie są błędami testów.

## Co faktycznie sprawdzono

1. Rejestracja syntetycznej tożsamości przez osobny origin dostawcy, Authorization
   Code + PKCE, RSA ID/access tokeny, serwerowa sesja i Free.
2. Rzeczywiste nawigacje formularzy przeglądarki do symulowanego Checkout,
   syntetyczny zakup 10 USD, podpisany webhook przez HTTP, sprawdzenie bieżących
   obiektów faktury/płatności/subskrypcji przez produkcyjną logikę PR #52 i Premium.
3. Portal, anulowanie na koniec okresu (nadal Premium), symulowany koniec czasu,
   odebranie uprawnienia oraz odmowa chronionej funkcji.
4. Logout unieważnia starą sesję, ponowne logowanie zachowuje UUID konta;
   odzyskiwanie dostępu otwiera stronę dostawcy (bez wysyłania prawdziwego e-maila).
5. Free nie omija zabezpieczeń przez URL success, localStorage, parametry planu,
   customer/price/subscription/user ID, inny istniejący UUID Premium ani JSON API
   bez access tokenu. Brak CSRF lub obcy Origin kończą się odmową.
6. Błędne/replayed state, callback z innej przeglądarki, cookie fixation,
   wygasła sesja, błędna sygnatura webhooka, obcy Host, mobile bez poziomego
   overflow oraz nagłówki ochronne. W HTML brak tokenów i sekretów.
7. Oddzielne testy prawdziwych podpisów RSA: nonce, issuer, audience, subject,
   scope, verified email, at_hash, azp, wygaśnięcie, obcy klucz. Hash sesji w DB,
   zaszyfrowane dowody logowania, pojedyncze użycie i rotacja klucza Fernet.
8. Realna fabryka ma ciasteczko `__Host-`/Secure i nie udostępnia tras symulatora.

## Granice wyniku

**To kontrolowane E2E, nie potwierdzenie integracji z tenantem Auth0 i kontem
Stripe.** Kryptografia, sesje, SQL, transakcje, polityka autoryzacji, HTTP i
Chromium są rzeczywiste. Zewnętrzny transport OIDC/Stripe oraz upływ miesiąca
są zastąpione jawnymi fixture'ami. Nie używano kluczy ani API dostawców.

Syntetyczna rejestracja reprezentuje już zweryfikowaną tożsamość. Faktyczne
e-mail verification, reset hasła, MFA, polityki Auth0, consent/logout prompt,
JWKS rotation na żywej usłudze, 3DS/SCA, odnowienia i hosted Stripe Portal
wymagają testu z konfiguracją właściciela. Realny adapter nie tworzy klientów
Stripe z Test Clock; symulacja końca okresu nie dowodzi działania Test Clock.

Dokładne czynności i oczekiwane wyniki:
[instrukcja Auth0, Stripe Sandbox i PostgreSQL](AUTH0_STRIPE_DEMO_SETUP.md).

## Zrzuty — wyłącznie syntetyczne dane

| Etap | Obraz |
|---|---|
| Konto Free | [01-free.png](account-demo/screenshots/01-free.png) |
| Symulator Checkout | [02-simulated-checkout.png](account-demo/screenshots/02-simulated-checkout.png) |
| Premium po webhooku | [03-premium.png](account-demo/screenshots/03-premium.png) |
| Zaplanowane anulowanie | [04-cancellation-pending.png](account-demo/screenshots/04-cancellation-pending.png) |
| Free po wygaśnięciu | [05-expired.png](account-demo/screenshots/05-expired.png) |
| Telefon 390 px | [06-mobile.png](account-demo/screenshots/06-mobile.png) |

## Odtworzenie testów

Z repozytorium, w dedykowanym virtualenv:

```bash
python -m pip install -r requirements-billing-demo.txt 'pytest>=8,<10' 'playwright>=1.58,<2'
python -m playwright install chromium
DEMO_SCREENSHOT_DIR=test-results/screenshots DEMO_TRACE_DIR=test-results/traces \
  python -m pytest -q billing_backend/tests billing_demo/tests test_stripe_test_billing.py
```

Dla rzeczywistego PostgreSQL ustaw prywatnie:

```text
TEST_BILLING_DATABASE_URL=postgresql+psycopg://.../bestbets_billing_test
TEST_DEMO_DATABASE_URL=postgresql+psycopg://.../bestbets_demo_test
```

Obie bazy mają być lokalne, dedykowane i pozbawione realnych danych. **Zestaw
backendu usuwa i odtwarza tabele swojej bazy testowej.** Nie kieruj go na bazę
demonstratora z danymi, które chcesz zachować. Testy demo nie mogą korzystać
z tego samego pliku SQLite co równolegle uruchomiony podgląd.

Workflow `BestBets isolated account demo` powtarza zestaw na SQLite i PostgreSQL
16, sprawdza migracje i niezmienność publicznej aplikacji. Artefakty zawierają
JUnit, screenshoty i trace'y syntetycznej sesji. Trace'y oglądaj lokalnie:
`python -m playwright show-trace test-results/traces/NAZWA_TESTU.zip`.
Nie zbieraj ani nie publikuj takich trace'ów z prawdziwymi tokenami lub danymi.

[Maszynowy zapis wyników](ACCOUNT_DEMO_TEST_RESULTS.json).
