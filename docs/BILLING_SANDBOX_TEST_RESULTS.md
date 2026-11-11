# Walidacja backendu abonamentów — Sandbox

Testowany lokalnie 11 listopada 2026. Python 3.12.14, Stripe SDK 13.2.1,
FastAPI 0.141.1, SQLAlchemy 2.1.8, Alembic 1.20.1, PyJWT 2.13.0.

| Grupa | Wynik |
|---|---|
| Backend, API i adapter z PR #44 na SQLite | 84/84 |
| Te same testy na rzeczywistym PostgreSQL 17.11 | 84/84 |
| Istniejące regresje NBA/UI oraz legacy gateway (`unittest discover`) | 207/207 |
| Alembic PostgreSQL: initial upgrade + schema check | OK |
| SQLite: initial upgrade + schema check | OK |
| Kompilacja Pythona i `git diff --check` | OK |
| Publiczny `app.py`, HTML/CSS, assets i `requirements.txt` | Brak zmian względem `main` |
| Wzorce rzeczywistych sekretów w kodzie/docs/testach | Nie znaleziono |

Grupy testów częściowo się pokrywają — wyników nie należy sumować jako liczby
unikalnych scenariuszy. PostgreSQL był uruchomiony tylko lokalnie, z syntetycznymi
rekordami, niezależnie od SQLite. CI ma też własny PostgreSQL 16 i osobną macierz.

## Co rzeczywiście sprawdzono

- Prawdziwe podpisy RSA tokenów JWT, zły issuer/audience/podpis, wygasły token,
  zbyt długi TTL, brak zweryfikowanego e-maila i niewłaściwy scope.
- Własność konta i brak łączenia po e-mailu; klient nie może nadać Premium rolą,
  query stringiem, cudzym UUID, customer ID, Price ani success URL.
- Właściwy plan USD 10 / miesiąc / quantity 1, brak dostępu dla trialing,
  incomplete, past_due, unpaid, paused lub canceled.
- Dowód faktury i płatności z tego samego okresu/właściciela; brak dostępu dla
  processing/niezapłaconej faktury, niepełnej wpłaty, refund/dispute lub złych ID.
- Ochrona body i origin, trwałe limity, brak sekretów w reprezentacji konfiguracji.
- HMAC webhooka w oficjalnym SDK: dokładne bajty, zmieniony payload, stary podpis,
  przyszły timestamp, brak podpisu, event live i Connect.
- Unikalność zdarzenia i hash treści, out-of-order, rollback przy awarii dostawcy,
  unieważnienie poprzedniego cache allow i ponowienie bez utraty zdarzenia.
- Cztery równoległe webhooki — jedna operacja skutku w bazie; cztery równoległe
  karty — jedna sesja Checkout. Sprawdzone także na PostgreSQL z blokadami wierszy.
- Trwały UUID próby przed wywołaniem Stripe, ponowienie po utracie odpowiedzi,
  odzyskanie próby po terminie i zachowanie deduplikacji po restarcie serwisu.
- Brak drugiej opłaty przy zakończonym Checkout/istniejącej subskrypcji,
  przywiązanie otwartej próby do zaakceptowanego Price i wersji informacji.
- Portal własnego klienta i konfiguracja bez zmiany planu, z anulowaniem na koniec
  okresu. Anulowanie zachowuje dostęp do opłaconego terminu, potem go odbiera.
- Wygaśnięcie lease/okresu, awaria Stripe i okresowa rekoncyliacja.

## Granice tych wyników

Transport Stripe i transport klucza OIDC są zastąpione fixture'ami. Sygnatury,
walidacja, HTTP ASGI, SQL, constraints, transakcje i współbieżność są rzeczywiste.
Nie użyto sekretów, nie wykonano transakcji ani faktycznych wywołań konta Stripe.
**To nie jest pełny E2E z Stripe Sandbox i dostawcą OIDC.**

Pozostają do zatwierdzonego, ręcznego E2E: rejestracja/logowanie u wybranego IdP,
JWKS rotation, SCA, testowe odnowienie i błędy karty, hosted Portal, kompatybilność
przypiętej wersji API z wybranym Sandbox oraz realne dostarczanie webhooków.
Żaden z tych punktów nie jest oznaczony jako zaliczony.

Dwie lokalne uwagi środowiskowe to ostrzeżenia o przyszłych zmianach interfejsu
pytest/AnyIO i Starlette TestClient, bez nieudanych asercji. Jeden przestarzały
root test v9 oczekiwał nieistniejącego już punktu wejścia; poprawiono asercję do
faktycznego `bestbets_custom_screen`, bez zmiany publicznej aplikacji.

[Architektura i uruchomienie](BILLING_SANDBOX_ARCHITECTURE.md) ·
[Wyniki maszynowe](BILLING_SANDBOX_TEST_RESULTS.json)
