# HOOPZARO — administrator i uprawnienia Premium

Ten projekt używa tożsamości OpenID Connect (OIDC) w Streamlit (`st.login`,
`st.user`, `st.logout`). Nie używa adresów IP, haseł w repozytorium ani stanu
przesłanego z JavaScript do przyznawania uprawnień.
`requirements.txt` instaluje `streamlit[auth]` razem z wymaganym Authlib;
bez tego samo skonfigurowanie sekretów nie uruchomi logowania.

## Konfiguracja w Streamlit Community Cloud

1. Utwórz projekt OAuth/OIDC u dostawcy (np. Google Identity) i skonfiguruj
   przekierowanie `https://bestbets-nba.streamlit.app/oauth2callback` (po zmianie
   domeny: odpowiednio zaktualizuj przekierowanie).
2. Otwórz **Manage app → Settings → Secrets**. Wprowadź, uzupełniając własnymi
   wartościami, poniższy przykład. Nigdy nie zapisuj prawdziwego sekretu
   dostawcy w GitHubie ani w rozmowie.

```toml
[auth]
redirect_uri = "https://bestbets-nba.streamlit.app/oauth2callback"
cookie_secret = "UZUPELNIJ_LOSOWY_TAJNY_KLUCZ"
client_id = "UZUPELNIJ_OIDC_CLIENT_ID"
client_secret = "UZUPELNIJ_OIDC_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[access]
admin_emails = ["TWOJ_ZWERYFIKOWANY_EMAIL_KONTA_GOOGLE"]
admin_subjects = []
premium_emails = []
premium_subjects = []
```

3. Przeładuj aplikację i otwórz **Ustawienia → Zaloguj się**. Konto z adresem
   `admin_emails` otrzyma dostęp Premium bez opłaty, tylko jeśli Google zwróci
   potwierdzone `email_verified = true`. Można zamiast adresu użyć trwalszej
   pary `issuer|subject` w `admin_subjects`.
4. Konta bez uprawnień widzą wyłącznie darmowy podgląd; model Premium nie
   trafia do ich przeglądarki. Uprawnienia są weryfikowane ponownie przy każdym
   żądaniu danych.

## Płatne konta

`premium_emails` i `premium_subjects` są **ręczną listą uprawnień**, możliwą
do użycia do pilotażu. Nie są zamiennikiem automatycznej subskrypcji. Przed
uruchomieniem Stripe należy zweryfikować usługę, wdrożyć bezpieczny webhook,
bazę subskrypcji i sprawdzanie aktywnego statusu płatności. Samo kliknięcie
przycisku Premium ani zmiana parametrów URL nie może odblokowywać danych.

## Model i weryfikacja

Rozkład wyników używa 5000 losowań, szacowanego wyniku i zmienności na
podstawie *wyłącznie zakończonych meczów sprzed spotkania*. Gdy dostępna jest
świeża kopia NBA Advanced, używa też oficjalnych `PACE`, `OFF_RATING` i
`DEF_RATING`. Pozostałe źródła (miejsce gry, przerwy, rywale i historia
kontuzji) są prezentowane jako kontekst, lecz nie wywołują arbitralnych
"bonusów" punktowych. To model eksperymentalny; nie gwarantujemy poprawy
precyzji bez niezależnego backtestingu na kolejnych meczach.

## Nieprzechodzący tracker GitHub Actions

Automatyczny tracker wymaga trwałego magazynu. Ustaw w repozytorium GitHub
Actions sekret `TRACKER_DATABASE_URL` z adresem właściwej, własnej bazy
PostgreSQL. Bez niego zaplanowane zadanie celowo kończy się błędem i nie
zapisuje prognoz. Nie konfiguruj magazynu przez zastąpienie go plikiem
lokalnym w GitHub Actions — dane znikają wraz z maszyną runnera.
