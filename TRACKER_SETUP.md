# BestBets v7.5 — trwały Performance Tracker

## Dwie metody przechowywania

- **Domyślnie:** lokalny SQLite w `data/pregame_forecasts.sqlite3`. Działa bez konfiguracji, ale na Streamlit Community Cloud nie jest trwały. Baza może zniknąć przy restarcie i nie synchronizuje się między instancjami.
- **Opcjonalnie:** własny PostgreSQL. Dane przeżywają ponowne wdrożenia aplikacji i trafiają do tej samej bazy niezależnie od serwera Streamlit.

Aby użyć PostgreSQL, najpierw utwórz prywatną bazę PostgreSQL u dostawcy, który umożliwia połączenie SSL/TLS. W panelu Streamlit Cloud otwórz App settings → Secrets i dodaj:

```toml
TRACKER_DATABASE_URL = "postgresql://<uzytkownik>:<haslo>@<host>:5432/<nazwa>?sslmode=require"
```

Powyższy ciąg jest **szablonem**, nie rzeczywistymi danymi. Hasło i adres bazy trzymaj wyłącznie w Secrets, nigdy w GitHubie ani w kodzie aplikacji. Przeznacz osobnego użytkownika bazy i ogranicz mu uprawnienia do tabeli Trackera. Nie włączaj publicznego dostępu do danych prognoz.

Po zapisaniu sekretu uruchom ponownie aplikację. Zakładka `📈 Performance Tracker` wskaże magazyn `PostgreSQL — trwałe przechowywanie prognoz`. W pierwszym połączeniu aplikacja utworzy tabelę `bestbets_forecasts`.

**Ważne:** włączenie PostgreSQL **nie migruje** automatycznie danych z lokalnego SQLite. Lokalną historię trzeba osobno wyeksportować i zweryfikować; nie tworzymy nieprawdziwych rekordów przedmeczowych. Zapis następuje tylko po otwarciu zakładki symulacji **przed** startem meczu. Nie jest to jeszcze pełne monitorowanie bezobsługowe — potrzebny byłby harmonogram zadań z serwerem lub GitHub Actions i trwałą bazą.

## Audyt

Prognoza jest zapisywana jednokrotnie na identyfikator meczu ESPN. Powtórne wejście na stronę nie aktualizuje dawnych prawdopodobieństw. Zapisywany jest identyfikator wariantu modelu: `legacy_v72` albo `research_form_v74`. Dane wyników są dodawane tylko po oficjalnym zakończeniu spotkania według ESPN. Nie należy uśredniać statystyk modeli bez rozróżnienia wariantu.

Korekty formy, siły rywali, przewagi parkietu, odpoczynku i kalibracji są nadal eksperymentalne. Dni odpoczynku i back-to-back w v7.5 są metadanymi, **nie** mnożnikiem szans zwycięstwa.
