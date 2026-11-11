# BestBets × Stripe — Sandbox, bez publicznego wdrożenia

Pierwotny adapter z PR #44 został przejrzany i wykorzystany w osobnym backendzie
`billing_backend/`. Nie jest importowany przez `app.py`. Nie zmieniono publicznego
HTML/CSS, logo, wykresów, modeli NBA ani układu aplikacji.

**[Architektura, audyt bezpieczeństwa, uruchomienie i bramki przed wdrożeniem](BILLING_SANDBOX_ARCHITECTURE.md)**

## Ocena PR #44

Dobre podstawy: testowe klucze, podpis na surowym webhooku, odrzucanie zdarzeń
live, stały Price po stronie serwera, hosted Checkout/Portal i wyraźne oddzielenie
od Streamlit. Ten adapter sam nie stanowił systemu subskrypcji.

Luki do uzupełnienia przed nadaniem rzeczywistych uprawnień:

1. Brak uwierzytelniania i trwałego powiązania konta z klientem Stripe.
2. Brak transakcji, deduplikacji zdarzeń i obsługi zdarzeń poza kolejnością.
3. Helper `has_premium_access(status)` dopuszczał `trialing` i nie weryfikował
   planu, zapłaty, okresu, zwrotu ani właściciela. Pozostaje wyłącznie legacy
   podpowiedzią statusu; **backend autoryzuje przez `BillingService.require_premium`**.
4. Globalne `sdk.api_key` mogło mieszać konfiguracje klientów w jednym procesie.
5. Brak gwarancji, że Price oznacza dokładnie 10 USD / miesiąc / 1 sztukę.
6. Brak egzekwowania własności klienta w endpointach, limitów żądań i trwałych
   prób Checkout na wypadek timeoutu lub równoległych kart.
7. Brak sprawdzenia faktycznego Stripe Account i konfiguracji Portal.
8. Brak kryptograficznych testów OIDC/webhooków i testów na PostgreSQL.

Nowy backend uzupełnia te elementy. W adapterze wyłączono globalną zmianę klucza,
zaostrzono walidację odpowiedzi i URL, odrzucono Connect i dodano powiadomienia
refund/dispute. Zachowano zgodność odczytu legacy i nowszych pól webhooków faktur.
SDK jest przypięte do Stripe 13.x, a żądania API do `2025-02-24.acacia`.
Nowa autoryzacja wymaga opłaconego okresu; nie oferujemy dostępu trial/past_due.

## Konfiguracja

Instaluj `requirements-billing-sandbox.txt` wyłącznie dla osobnego API.
Sekrety wprowadzaj przez środowisko/manager sekretów, **nie do rozmowy ani GitHub**.
Lista zmiennych jest w dokumencie architektury. Nie skonfigurowano w tej pracy
prawdziwego konta OIDC ani sekretów Stripe; testy transportu Stripe są offline.

PR #44 odnotował historyczne ujawnienie testowego klucza na zrzucie. Przed
manualnym E2E należy go unieważnić i zastąpić w panelu Stripe. Nie odczytywano,
nie kopiowano i nie sprawdzano jego wartości w tej pracy.

## Przed rzeczywistymi płatnościami

Stripe wymienia m.in. „sports forecasting or odds-making with a monetary or
material prize” na liście ograniczonych/zabronionych modeli biznesowych.
Nie rozstrzygamy samodzielnie, jak Stripe zaklasyfikuje BestBets. Konieczne jest
**pisemne potwierdzenie Stripe dla rzeczywistego modelu NBA / Player Props /
analiz zakładów sportowych**, jurysdykcji i kanałów sprzedaży.

Źródła sprawdzone 11 listopada 2026:

- https://stripe.com/en-pl/legal/restricted-businesses
- https://docs.stripe.com/billing/subscriptions/webhooks
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/api/checkout/sessions/create
- https://docs.stripe.com/customer-management

Nie przełączaj tego backendu na live: odrzuca takie klucze i obiekty. Dopiero
po akceptacji procesora, przeglądzie prawnym, konfiguracji IdP i pełnym Sandbox
E2E może powstać osobny przeglądany adapter live. Ten PR niczego nie wdraża.
