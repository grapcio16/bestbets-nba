# BestBets V2 — wizualne odwzorowanie referencji premium

**Dotyczy tylko testowej strony uruchamianej przez \`preview_v2.py\`.**
Wersja produkcyjna \`app.py\`, oryginalny dokument v1, źródła NBA i logika
wyszukiwania pozostają bez zmian. Nowa gałąź bazuje na PR #48 (zwarte słupki).

## Co odtworzono z drugiego zdjęcia użytkownika

- Logo po lewej i podpis \`NBA ANALYTICS\`, pomarańczowy narożnik i dolny neon.
- Czytelne, jednolite wektorowe ikony menu; proporcje przycisków i wyszukiwarki.
- Granatowe gradienty, świecące cyjanowe/pomarańczowe kontury, zielone akcenty.
- Większy portrait/hero z nazwiskiem, metrykami i łukiem MATCHUP GRADE.
- Kolumny: **węższy wykres i wyraźniejszy prawy blok statystyk** zamiast
  poprzedniego ekstremalnie szerokiego wykresu.
- Wykres z rzeczywistymi meczami zachowuje zbite kolumny z PR #48. Oś i
  siatka reagują na szerokość panelu, słupki reagują na liczbę meczów.
- Dolne sześć kart ma zwiększoną widoczność, style narożników, obramowania,
  czytelne rzędy oraz lokalne logotypy/fallbacki drużyn.
- Profil i szukanie mają wektorowe ikony, przycisk X czyści pole zapytania.
- Karta Centrum pokazuje imię aktualnie wybranego zawodnika, gdy jest dostępny
  i nie udaje, że puste symulacje lub typy dzienne są policzone.

## Uczciwe ograniczenie 1:1

Referencja jest **makietą graficzną** — zawiera niepotwierdzone liczby
symulacji, fikcyjne/niezweryfikowane oznaczenia A−, przewidywane mecze i
wzorcowe portrety. Z tego powodu w działającym BestBets wartości pozostają
powiązane z prawdziwym wynikiem \`_research\`, a brakujące funkcje
pokazują kreski lub tekst pomocniczy. **Nie kopiujemy zrzutu jako obrazu tła,
nie wpisujemy fałszywych wyników i nie zmieniamy koloru słupków na zielony,
jeśli dla zakładu UNDER jest to przegrana.**

Wygląd docelowy jest odtwarzany CSS/HTML/SVG, ale nie należy traktować go jako
potwierdzonego porównania piksel-do-piksela w Operze. Rozdzielczości, fonty,
antyaliasing, portrait NBA oraz bieżący rynek i okres mogą się różnić.

## Test podglądu w Streamlit Community Cloud

Repozytorium: \`grapcio16/bestbets-nba\`

Gałąź: \`feature/bestbets-v2-reference-visual-20261111\`

Plik startowy: \`preview_v2.py\`

Uruchom tę konfigurację jako *oddzielną aplikację testową*. W Operze:
- ustaw zoom 100%, Ctrl+F5;
- sprawdź interfejs przy 1920×1080 i 1366×768;
- przełącz L5/L10/Season, PTS/REB/AST/3PM/PRA, OVER i UNDER;
- sprawdź logowanie i boczne ikony; **logowanie i subskrypcje nie są jeszcze
  wdrożone**, ikonki profilu i powiadomień są dekoracyjnymi podglądami;
- sprawdź przewijanie dolnych kart na telefonie.

Dla testów automatycznych:
\`python -m unittest discover -v\`

\`python test_v2_browser_preview.py\` przy uruchomionym \`preview_v2.py\`

\`python test_scaling_evidence.py\` przy równoległym produkcyjnym
\`app.py\` na porcie 8502. CI uruchamia te testy w dwóch wersjach Streamlit.

**Nie scalać do \`main\` bez akceptacji wyglądu użytkownika.**
