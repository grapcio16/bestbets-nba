# HOOPZARO V7.6 — badawczy tracker równoległy

**Status:** eksperyment, bez wpływu na wyniki publicznych symulacji.

## Hipotezy wybrane przed kolejnymi meczami

1. **Przewaga gospodarzy:** V7.5 może przeszacowywać gospodarzy. Wariant
   `auto_shadow_home_v76` odejmuje 0,75 pkt od prognozy gospodarza i dodaje
   0,75 pkt gościom (redukcja o połowę stałego bonusu parkietu wynoszącego
   łącznie 3 pkt w bazowych modelach). Inne korekty V7.5 i dane wejściowe
   pozostają identyczne. Nie zmieniamy sumy oczekiwanych punktów.
2. **Minuty zawodników:** `auto_player_minutes_v76` testuje małą korektę
   opartą na różnicy L3 i L10 rozegranych minut: `0,4 × (L3 − L10)`, z limitem
   ±3 minuty i dodatkowym limitem zmiany ±20% względem obecnej projekcji.
   Przy mniej niż sześciu występach pozostawia projekcję bez korekty.
   Punkty, zbiórki, asysty i trójki są przeskalowane proporcjonalnie do minut;
   pięć tysięcy symulacji zostaje uruchomione ponownie. To wyłącznie hipoteza
   o rotacji, a nie weryfikacja statusu kontuzji czy pierwszej piątki.

## Niezależność i bezpieczeństwo

- V7.2, V7.4, V7.5 i prognozy zawodników V7.4 zachowują dotychczasowe
  identyfikatory, wzory, dane i historię.
- Nowe prognozy uzyskują **oddzielne identyfikatory modeli**, są tworzone tylko
  przed rozpoczęciem meczu i zapisują się w append-only trackerze.
- Każdy wariant korzysta z tej samej zamrożonej historii oraz tego samego
  raportu ESPN co wariant kontrolny. Dane z przyszłości są odcinane.
- Błędy drugiego wariantu nie unieważniają poprawnie przygotowanej prognozy
  istniejącego modelu. Brak występu/DNP nie jest zerem.
- Harmonogram uruchamia modele badawcze **tylko** po ustawieniu środowiskowej
  flagi `HOOPZARO_V76_SHADOW_ENABLED=1`. Domyślnie jest wyłączona. Eksperyment
  nie zmienia widoków ani wyboru modelu przez użytkownika.

## Jak ocenić po nowych spotkaniach

1. Porównać pary V7.5–V7.6 dla dokładnie tych samych, rzeczywiście
   rozegranych spotkań. Mierzyć MAE sumy, MAE obu drużyn, błąd różnicy
   punktów, trafność zwycięzcy oraz Brier score. W wariancie parkietu suma
   oczekiwana z definicji się nie zmienia — ważna jest głównie różnica
   punktów, prognoza zwycięzcy i MAE drużyn.
2. Porównać V7.4–V7.6 na tych samych **rozliczonych występach zawodników**:
   MAE i bias minut, PTS, REB, AST, 3PM i PRA; osobno gracze z małą/dużą
   zmianą rotacji oraz DNP nierozliczone.
3. Raportować liczbę sparowanych obserwacji. Orientacyjnie poczekać na
   50–100 spotkań drużyn i kilkaset występów zawodników; to progi organizacyjne,
   nie gwarancja statystycznej istotności.
4. Nie dopasowywać parametrów do 16 już rozliczonych meczów — to dane, które
   zasugerowały hipotezy. Ocena wymaga nowego okresu prospektywnego. Nie
   nazywać wyników prognoz „trafnością zakładów” bez rzeczywistych linii.

## Aktywacja

Kod można wdrożyć bez zmiany publicznego wyboru modeli. Aby zbierać nowy
wariant w istniejącym automatycznym trackerze, ustawić
`HOOPZARO_V76_SHADOW_ENABLED=1` **w środowisku zaplanowanego zadania**.
Bez aktywacji można uruchamiać scenariusze lokalnie przez
`include_shadow_v76=True` (tracker spotkań) i `shadow_v76=True`
(tracker zawodników). Zapisy do produkcyjnej bazy wymagają zwykłych,
wcześniej skonfigurowanych uprawnień trackera.
