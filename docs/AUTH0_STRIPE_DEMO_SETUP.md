# BestBets: oddzielny demonstrator kont i subskrypcji

Publiczny `app.py`, HTML/CSS BestBets, routing NBA i dostęp do publicznej strony
pozostają bez zmian. Ten dokument dotyczy wyłącznie **lokalnego demonstratora**.
Kod bazuje na PR #52. Nie utworzono tenantów, użytkowników Auth0 ani zasobów Stripe.
Nie wykonano rzeczywistych wywołań tych usług ani płatności. Sekretów nie przesyłaj
w rozmowie, issue, zrzutach ekranu ani logach.

## 1. Wybór Auth0 i architektura

Auth0 Universal Login pasuje do standardu OIDC: dostawca utrzymuje hasła,
rejestrację, weryfikację e-maila, MFA i reset hasła. BestBets przechowuje wyłącznie
tożsamość `(issuer, sub)` i wewnętrzne UUID; nie łączy kont po samym e-mailu.
Nie potrzeba Management API ani uprawnień administratora Auth0 w aplikacji.

Przeglądarka → osobny BFF `billing_demo` → Auth0 Authorization Code + S256 PKCE.
Jednorazowy `state` jest związany z anonimową sesją. `nonce` i PKCE verifier są
szyfrowane Fernetem w bazie na maksymalnie 5 minut. Po callbacku serwer sprawdza
podpisy RS256, issuer, osobne audiences ID/access tokenu, nonce, czas ważności,
scope, verified-email, zgodność sub oraz `azp`/`at_hash`, gdy występują.

Przeglądarka otrzymuje losowe ciasteczko HttpOnly/SameSite=Lax, w HTTPS także
Secure i prefiks `__Host-`. Baza utrzymuje wyłącznie hash identyfikatora sesji.
Tokeny OIDC są odrzucane po callbacku, nie trafiają do HTML/localStorage/bazy.
Sesja trwa najwyżej 15 minut i nigdy dłużej niż zweryfikowane tokeny. Brak refresh
tokenów i `offline_access`. Po wygaśnięciu ponowne wejście do Universal Login
może skorzystać z istniejącego SSO Auth0.

BFF wywołuje tę samą usługę `BillingService` co API PR #52. Checkout/Portal
przyjmują UUID konta wyłącznie z sesji. Formularze mają CSRF oraz ścisły Origin;
obce/powtórzone pola są odrzucane. Premium sprawdza się przed wykonaniem
chronionej operacji, a nie przez widoczność przycisku. Publiczne analizy NBA
nie zostały podpięte pod tę demonstracyjną kontrolę.

Webhook pod `/api/webhooks/stripe` weryfikuje dokładne bajty, podpis i testowy
charakter zdarzenia, deduplikuje event i pobiera bieżące dowody płatności Stripe.
Powrót `?checkout=success`, status w przeglądarce lub rola OIDC nie nadają Premium.
Lease uprawnienia wynosi maksymalnie 60 sekund. Awaria weryfikacji zamyka dostęp,
zamiast przedłużać stary grant. Szczegóły dowodów: [architektura PR #52](BILLING_SANDBOX_ARCHITECTURE.md).

## 2. Czynności osobiste w Auth0 Dashboard

Nazwy zakładek mogą zależeć od wersji Dashboard. Wszystkie poniższe zasoby mają
być oddzielone od produkcji.

1. Utwórz tenant **Development**, rekomendowany region **EU**. Przed użyciem
   rzeczywistych danych uzgodnij DPA, regiony i transfery; EU nie zastępuje analizy RODO.
2. **Branding → Universal Login**: wybierz New Universal Login, bez własnych
   formularzy haseł w BestBets.
3. **Applications → APIs → Create API**:

   | Pole | Wartość |
   |---|---|
   | Name | BestBets Sandbox API |
   | Identifier | `https://bestbets-sandbox-api.example` (identyfikator, nie musi hostować strony) |
   | Signing Algorithm | RS256 |
   | Token Expiration | 900 sekund |
   | Permissions | `bestbets:api` |
   | Enable RBAC / Add Permissions in Access Token | wyłączone w tym demonstratorze |
   | Allow Offline Access | wyłączone |

   `bestbets:api` oznacza dostęp uwierzytelniony, nie Premium. Nie przypisuj
   Premium przez Auth0 role ani metadane możliwe do zmiany przez użytkownika.
4. **Applications → Applications → Create Application → Regular Web Application**:

   | Pole | Wartość lokalna |
   |---|---|
   | Name | BestBets Sandbox Demo |
   | Allowed Callback URLs | `http://localhost:8810/auth/callback` |
   | Allowed Logout URLs | `http://localhost:8810/` |
   | Allowed Web Origins | `http://localhost:8810` |
   | Token Endpoint Authentication Method | POST (`client_secret_post`) |
   | OIDC Conformant | włączone |
   | ID Token Expiration (Advanced Settings → OAuth) | **900 sekund**, domyślne 10 h nie przejdzie walidacji |
   | Grant Types | Authorization Code; bez Implicit, Password, Refresh Token |

   Nie dodawaj wildcardów, publicznego Streamlit ani `127.0.0.1` zamiennie z
   `localhost`. W przeglądarce używaj dokładnie `http://localhost:8810`.
   Auth0 może wyświetlać ekran zgody dla localhost; jest to spodziewane.
   Application Login URI można zostawić puste lokalnie. Nie dodajemy CORS z
   ciasteczkami ani przeglądarkowego wywoływania token endpointu.
5. **Authentication → Database → Connections**: utwórz lub wybierz oddzielne
   połączenie dla demonstratora. Włącz je dla tej aplikacji; rejestracja ma być
   dozwolona. Włącz weryfikację e-maila i reset hasła w Universal Login.
   Skonfiguruj nadawcę e-maili/szablony i dostarczalność; testowy nadawca Auth0
   ma ograniczenia. Włącz ochronę brute-force, breached-password i politykę MFA
   odpowiednią do kont testowych. Nie używaj własnego endpointu do resetowania hasła.
6. **Actions → Library → Create Action → Login / Post Login**: wklej kod z
   [`billing_demo/auth0/post-login.js`](../billing_demo/auth0/post-login.js),
   Deploy, następnie **Actions → Flows → Login**, dodaj Action i Apply.
   Jeśli zmieniłeś API Identifier, zmień też stałą w Action.
   Claim `https://bestbets-nba.streamlit.app/claims/email_verified` jest nazwą
   przestrzeni claimu, nie wywołaniem publicznej aplikacji.
7. Skopiuj Domain i Client ID do lokalnej konfiguracji. Client Secret zapisz
   bezpośrednio w swoim menedżerze sekretów lub lokalnym pliku z prawami 0600.
   Nie udostępniaj sekretu. Issuer i JWKS muszą używać tego samego Auth0 domain;
   issuer kończy się `/`. Nie mieszaj custom domain z domeną tenanta.

Po rejestracji Action może zakończyć pierwsze logowanie `access_denied`, dopóki
użytkownik nie potwierdzi e-maila. Otwórz wiadomość Auth0 i zaloguj się ponownie.
Przycisk „Odzyskaj dostęp” otwiera Universal Login; tam wybierz „Forgot password?”.
Rejestracja i odzyskiwanie dodają `prompt=login`, aby istniejące SSO nie pominęło
odpowiedniego ekranu. Zwykłe logowanie może korzystać z SSO.
Weryfikacja e-maila i rzeczywista dostarczalność resetu wymagają manualnego testu.

## 3. Czynności osobiste w Stripe Dashboard — tylko Sandbox

1. Wybierz **oddzielny Sandbox** w przełączniku kont/środowisk. Potwierdź, że
   klucz jest testowy. Nie kopiuj kluczy live, nie aktywuj płatności publicznych.
2. **Product Catalog → Add product**: BestBets Premium Sandbox, cena recurring
   **USD 10.00 / month**, interval_count=1, quantity=1, licensed. Bez trial,
   kuponów, promokodów i alternatywnych cen w tym demonstratorze. Zapisz Product
   `prod_…`, Price `price_…` oraz Account `acct_…` z ustawień konta.
3. **Settings → Billing → Customer portal**: zapisz testową konfigurację:
   - payment method update: włączone;
   - cancellation: włączone, **at end of billing period**;
   - subscription/plan updates: wyłączone;
   - historia faktur: zalecana;
   - return URL: `http://localhost:8810/` lokalnie lub osobny HTTPS demo origin.

   Potrzebne jest ID konfiguracji **`bpc_…`**, nie ID sesji `bps_…` ani link
   udostępnianego portalu. Gdy Dashboard nie pokazuje ID, odczytaj je we własnym
   Stripe CLI: `stripe billing_portal configurations list --limit 10` w tym samym
   Sandbox. Backend sprawdza wymagane opcje przed utworzeniem każdej sesji Portal.
4. Lokalnie zaloguj Stripe CLI do tego samego Sandbox (sprawdź wskazane konto).
   Następnie uruchom:

   ```bash
   stripe listen --forward-to http://localhost:8810/api/webhooks/stripe
   ```

   Klucz podpisu wypisany przez CLI zapisz prywatnie jako
   `STRIPE_TEST_WEBHOOK_SECRET`. Nie umieszczaj go w logach PR. Ten sekret różni
   się od sekretu endpointu Dashboard; używaj źródła, które faktycznie dostarcza
   webhook. Sama komenda `stripe trigger` tworzy niepowiązane przykłady i nie
   zastępuje zakupu Checkout z konta BestBets.
5. Dla późniejszego **osobnego HTTPS środowiska testowego** dodaj endpoint
   Workbench → Webhooks wskazujący `https://DEMO-HOST/api/webhooks/stripe`, zdarzenia
   z tego konta (bez Connect), wersja payload **2025-02-24.acacia** zgodna z
   adapterem PR #52. Subskrybuj:

   ```text
   checkout.session.completed
   customer.subscription.created
   customer.subscription.updated
   customer.subscription.deleted
   customer.subscription.paused
   customer.subscription.resumed
   invoice.paid
   invoice.payment_failed
   invoice.payment_action_required
   charge.refunded
   charge.dispute.created
   charge.dispute.closed
   ```

   CLI do testów lokalnych powinien przekazywać payload zgodny z tą wersją;
   zweryfikuj wersję w zdarzeniu/ustawieniach Sandbox. Nie zmieniaj wersji live.
6. Testowy secret API `sk_test_…` i webhook secret wpisz wyłącznie lokalnie.
   Nie trzeba publishable key: Checkout i Portal są hostowane przez Stripe.
   Nie używamy prawdziwych kart. Przykładowa karta testowa Stripe:
   `4242 4242 4242 4242`, przyszła data, dowolny testowy CVC. Oddzielnie wykonaj
   scenariusz 3DS zgodnie z dokumentacją Stripe Testing.

## 4. PostgreSQL i wszystkie zmienne środowiskowe

Utwórz dedykowaną bazę, np. `bestbets_demo_test`, i użytkownika bez superuser.
Nie używaj bazy aplikacji publicznej. Dla zdalnej bazy wymagane są TLS
`sslmode=verify-full`, zaufany certyfikat CA i weryfikacja hosta. Docelowo osobny
użytkownik migracyjny (DDL) i aplikacyjny (DML); zapewnij mu dostęp do obu nowych
tabel sesji. Przykład URL bez danych uwierzytelniających:
`postgresql+psycopg://bestbets_test@127.0.0.1:5432/bestbets_demo_test`.

Skopiuj `billing_demo/.env.example` do `billing_demo/.env`, nadaj plikowi 0600.
Puste pola uzupełnij prywatnie; plik jest ignorowany przez Git.

| Zmienna | Znaczenie / źródło |
|---|---|
| DEMO_ORIGIN | dokładnie `http://localhost:8810`, bez końcowego `/` |
| BESTBETS_APP_URL | ten sam origin; wyłącznie demo, nie publiczny Streamlit |
| DEMO_ALLOW_LOCAL_HTTP | `true` tylko dla loopback HTTP; `false` dla HTTPS |
| DEMO_STATE_ENCRYPTION_KEY | prywatny losowy klucz Fernet, wspólny dla workerów |
| BILLING_DATABASE_URL | prywatny URL dedykowanej bazy PostgreSQL |
| BILLING_ALLOW_SQLITE_TEST | `false` dla tej konfiguracji |
| OIDC_ISSUER | `https://YOUR-TENANT.eu.auth0.com/` |
| OIDC_JWKS_URL | `https://YOUR-TENANT.eu.auth0.com/.well-known/jwks.json` |
| OIDC_API_AUDIENCE | API Identifier z Auth0 |
| OIDC_EMAIL_VERIFIED_CLAIM | `https://bestbets-nba.streamlit.app/claims/email_verified` |
| OIDC_CLIENT_ID | Client ID Regular Web Application |
| OIDC_CLIENT_SECRET | prywatny Client Secret tej aplikacji |
| STRIPE_TEST_ACCOUNT_ID | `acct_…` testowego konta |
| STRIPE_TEST_SECRET_KEY | prywatny `sk_test_…` z tego Sandbox |
| STRIPE_TEST_PRODUCT_ID | `prod_…` |
| STRIPE_TEST_PRICE_ID | `price_…` za 1000 centów USD miesięcznie |
| STRIPE_TEST_PORTAL_CONFIGURATION_ID | `bpc_…` z tego Sandbox |
| STRIPE_TEST_WEBHOOK_SECRET | prywatny `whsec_…` z CLI albo endpointu |
| BILLING_TERMS_VERSION | `sandbox-draft-v1`, wyłącznie niezatwierdzona wersja demo |

Wygeneruj klucz Fernet **lokalnie** i zapisz wynik prywatnie, bez commitowania:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Rotacja klucza unieważnia trwające logowania (nie hasła ani konta); przechowuj
go w menedżerze sekretów. Sesje i dane testowe wymagają zaplanowanej retencji.

## 5. Uruchomienie realnego połączenia Sandbox po konfiguracji

Z katalogu repozytorium, na tej gałęzi, w osobnym virtualenv:

```bash
python -m pip install -r requirements-billing-demo.txt
python -m billing_demo --env-file billing_demo/.env migrate
python -m billing_demo --env-file billing_demo/.env serve
```

Otwórz **http://localhost:8810/**. Serwer wiąże tylko 127.0.0.1; wyłączone są
access logi i zaufanie do nagłówków proxy. Nie hostujemy ani nie wdrażamy go
automatycznie. Dla zdalnego demo osobno skonfiguruj HTTPS/reverse proxy,
konkretny origin i allowlisty Auth0, redakcję logów callbacku oraz odpowiednie
uruchomienie ASGI. Endpointy tokenów/JWKS używają weryfikowanego HTTPS.

Okresowo uruchamiaj (np. co minutę) `reconcile`, a `cleanup` co godzinę:

```bash
python -m billing_demo --env-file billing_demo/.env reconcile
python -m billing_demo --env-file billing_demo/.env cleanup
```

Zablokowanie konta w lokalnej tabeli `billing_accounts.disabled` działa od
następnego żądania. Zablokowanie wyłącznie w Auth0 nie wycofuje wydanych JWT:
bez dodatkowej integracji administracyjnej bieżąca sesja może trwać do 15 minut.
Logout unieważnia bieżącą sesję lokalną; OIDC logout Auth0 bez token hints może
poprosić o potwierdzenie. Zatwierdź je, aby zamknąć też SSO dostawcy. To nie jest
funkcja „wyloguj wszystkie urządzenia”. Reset hasła i MFA testuj u dostawcy.

## 6. Działający lokalny podgląd bez usług zewnętrznych

Ten tryb **symuluje** Auth0 i Stripe. Nie wysyła e-maili, nie przechowuje haseł,
nie sprawdza dostarczalności, 3DS, rzeczywistych API, tenant policy ani live usług.
Syntetyczna rejestracja oznacza od razu potwierdzoną tożsamość. Ekrany mają
widoczną etykietę SYMULATOR. Nie wpisuj prawdziwych danych.

```bash
python -m pip install -r requirements-billing-demo.txt
python -m billing_demo.testing.runner --controlled-demo \
  --database-url postgresql+psycopg://bestbets_test@127.0.0.1:5432/bestbets_demo_test
```

Alternatywa bez PostgreSQL wyłącznie do lokalnej demonstracji:

```bash
python -m billing_demo.testing.runner --controlled-demo \
  --database-url sqlite:////tmp/bestbets-demo-preview.sqlite3
```

Otwórz http://localhost:8810, załóż syntetyczne konto z aliasem, kup symulowany
plan, otwórz Portal i anuluj. Plan nadal jest Premium. Ponownie otwórz Portal
i wybierz „Symuluj koniec opłaconego okresu”: plan zmieni się na Free.
Kontrolowany provider dostarcza podpisany webhook przez prawdziwy HTTP, a backend
weryfikuje dowody przy użyciu prawdziwego Stripe SDK, SQL i transakcji.
Serwery wiążą tylko loopback, nie odczytują kluczy dostawców z otoczenia i
odmawiają uruchomienia na innej bazie niż lokalna `*_demo_test` lub wskazany
prefiks pliku SQLite. Dane użytkowników symulatora są w pamięci; restart oznacza
nowe syntetyczne tożsamości, nie migrację realnych kont. Ten adapter **nigdy nie
jest wybierany przez realną fabrykę aplikacji ani parametry żądania**.

## 7. Manualny test prawdziwego Auth0 i Stripe Sandbox — do wykonania

1. Zarejestruj nowe testowe konto przez Universal Login. Przed potwierdzeniem
   e-maila logowanie ma być odrzucone; potwierdź link i zaloguj się ponownie.
2. Sprawdź Free, próbę wejścia `/premium/demo` (403), reset hasła przez Auth0,
   ponowne logowanie i ten sam UUID. Sprawdź MFA oraz zamknięcie SSO przy logout.
3. Akceptuj dwa testowe checkboxy i otwórz rzeczywisty testowy Checkout.
   Zapłać kartą testową. Zobacz podpisany webhook w CLI/Workbench; odśwież status
   na serwerze. Dopiero wtedy Premium i `/premium/demo` mają działać.
4. Powtórz na oddzielnych kontach z odmową płatności i 3DS. Success URL albo
   niezakończona płatność nie mogą przyznać dostępu. Przy błędach usługi zobaczysz
   503, bez starego zezwolenia. Nie utożsamiaj opóźnionego webhooka z opłaceniem.
5. W Customer Portal anuluj na koniec okresu. Oczekuj `cancel_at_period_end=true`
   **i nadal Premium** aż do `paid_until`. Pełny cykl czasu testuj oddzielnie
   test clockiem Stripe po zaprojektowaniu tworzenia klientów z clockiem; obecny
   realny adapter nie tworzy klientów z test_clock. Lokalny przycisk symuluje czas.
6. Aby bez czekania sprawdzić odebranie uprawnienia przez prawdziwy Stripe,
   w tym samym Sandbox anuluj tę testową subskrypcję **natychmiast** w Dashboard.
   To osobny scenariusz od anulowania na koniec miesiąca. Zweryfikuj webhook,
   Free i 403. Sprawdź również refund, dispute, utratę i ponowienie webhooka.
7. Drugi użytkownik Free nie może zmienić swojego planu przez UUID, customer,
   price, parametry URL, cookies ani localStorage. Testy automatyczne pokrywają
   te granice; nie uruchamiaj skanów przeciw publicznej stronie.

**Ten manualny zestaw nie został jeszcze wykonany.** Po konfiguracji przez
właściciela wymaga odnotowania wyników bez sekretów i danych osobowych.

## 8. Warunki dalszego rozwoju

Nie ma aktywnego publicznego paywalla. Nie ma przełącznika live. Przed prawdziwymi
płatnościami potrzebne są pisemna akceptacja Stripe dla rzeczywistego modelu
analiz/prognoz zakładów sportowych, osobna zgoda na wdrożenie i przegląd prawny.
Cena 10 USD jest tu testową ceną planu; brutto/netto, VAT/sales tax, zwroty,
odstąpienie, reklamacje, regulamin, obowiązki konsumenckie, retencja i RODO nie
są uznane za prawnie zatwierdzone. Dane kart obsługuje hostowany Stripe.

Źródła konfiguracji: [Auth0 Universal Login](https://auth0.com/docs/authenticate/login/auth0-universal-login),
[Authorization Code + PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce),
[Auth0 custom claims](https://auth0.com/docs/secure/tokens/json-web-tokens/create-custom-claims),
[Auth0 OIDC logout](https://auth0.com/docs/authenticate/login/logout/log-users-out-of-auth0),
[Stripe Portal](https://docs.stripe.com/customer-management/configure-portal),
[Stripe webhooks](https://docs.stripe.com/webhooks),
[Stripe test cards](https://docs.stripe.com/testing).
