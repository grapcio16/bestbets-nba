# Hoopzaro — Polityka prywatności
**PROJEKT DO ZATWIERDZENIA • wersja 0.1 • 26.11.2026**
Nie publikować jako obowiązującego dokumentu przed uzupełnieniem pól w nawiasach kwadratowych, potwierdzeniem dostawców, retencji i rzeczywistego zakresu przetwarzania. Opis przyszłych funkcji nie oznacza ich uruchomienia.

## 1. Administrator i kontakt
Administratorem danych związanych z serwisem Hoopzaro (hoopzaro.com oraz jego instancją hoopzaro.streamlit.app) jest [pełne imię i nazwisko administratora albo pełna nazwa przedsiębiorcy], [adres do kontaktu prawnego, państwo]. Kontakt w sprawach danych: contact@hoopzaro.com; sprawy techniczne: support@hoopzaro.com. [Inspektor ochrony danych: dane kontaktowe, jeżeli został wyznaczony.] Polityka dotyczy użytkowników serwisu, nie zawodników NBA, których dane sportowe analizuje serwis.

## 2. Dane i cele
- Logowanie Google: od dostawcy tożsamości otrzymujemy identyfikator wystawcy i użytkownika (iss, sub), informacje o ważności uwierzytelnienia oraz zależnie od odpowiedzi dostawcy imię/nazwę, e-mail i informację o jego weryfikacji. Służą do uwierzytelnienia, rozpoznania konta i nadania uprawnień. Nie otrzymujemy hasła do Google. Podstawa: art. 6 ust. 1 lit. b RODO w zakresie świadczenia usługi, o którą użytkownik występuje; bezpieczeństwo i zapobieganie nadużyciom: lit. f, po udokumentowanej ocenie interesów.
- Korzystanie z serwisu: dane wejściowe analiz, ustawienia sesji i wyniki potrzebne do działania funkcji. Nie są zapisywane jako treści zapytań w opisanej niżej telemetrii. Podstawa: lit. b.
- Dane techniczne: dostawcy hostingu i infrastruktury mogą przetwarzać adres IP, informacje o przeglądarce, logi połączeń i błędów w związku z dostarczeniem i ochroną usługi. Podstawa: lit. b lub lit. f, odpowiednio do celu. [Uzupełnić rzeczywisty zakres, odbiorców oraz okresy logów.]
- Dobrowolna analityka użytkowania (przed uruchomieniem): pseudonimowy identyfikator HMAC konta zalogowanego, ostatnia obserwowana rola, daty pierwszej i ostatniej obserwacji, losowy identyfikator sesji bez powiązania go w bazie z identyfikatorem konta, odwiedzane zakładki, próbki przybliżonego czasu aktywności oraz agregaty wywołań funkcji, błędów i czasu wykonywania. Cel: ulepszanie funkcji, wykrywanie problemów technicznych i ocena wykorzystania aplikacji. Podstawa: dobrowolna zgoda (art. 6 ust. 1 lit. a). W tej telemetrii nie zapisujemy e-maili, adresów IP, treści zapytań ani danych kart. Nie oznacza to, że wszystkie usługi infrastrukturalne nie przetwarzają tych danych. Pseudonimizacja nie jest anonimizacją.
- Kontakt i wsparcie: adres e-mail, treść wiadomości i dane niezbędne do obsługi zgłoszenia. Podstawa: lit. b, gdy wiadomość dotyczy usługi lub działań przed zawarciem umowy; lit. f w zakresie pozostałego kontaktu i obrony roszczeń; lit. c, jeśli wymaga tego prawo.
- Płatności i subskrypcje (obecnie tylko środowisko testowe): Stripe obsługuje stronę płatności. Przed uruchomieniem płatności rzeczywistych serwis przewiduje przetwarzanie identyfikatorów klienta, sesji płatności, subskrypcji, statusu i okresu dostępu oraz informacji rozliczeniowych potrzebnych do realizacji umowy. Nie przewidujemy przechowywania pełnych danych karty przez Hoopzaro. Podstawa po uruchomieniu: lit. b, lit. c (obowiązki rozliczeniowe) oraz lit. f (przeciwdziałanie nadużyciom, dochodzenie roszczeń). [Potwierdzić rzeczywiste przepływy, podmioty Stripe, okresy i podstawy przed publikacją.]
- Uprawnienia i limity: niezbędne identyfikatory konta i status uprawnienia mogą służyć wykonaniu usługi i ograniczeniu nadużyć; ewentualny limit dzienny musi być niezależny od zgody analitycznej. [Potwierdzić wdrożenie limitów, okresy i podstawę.]

Brak logowania ogranicza dostęp do funkcji wymagających konta. Odmowa analityki nie ogranicza dostępu do funkcji, których użytkownik jest uprawniony używać. Dane wymagane dla przyszłej płatności zostaną wskazane w procesie zakupu.

## 3. Zgoda i jej wycofanie
Analityka klientów ma być domyślnie wyłączona. Po uruchomieniu można wybrać „Zezwól na analitykę” w Ustawieniach; zgoda dotyczy bieżącej sesji i jest odwoływalna w tym samym miejscu. Wycofanie kończy dalsze zbieranie danych i nie podważa zgodności wcześniejszego przetwarzania opartego na ważnej zgodzie. Nie oznacza automatycznego usunięcia wszystkich dotychczasowych danych. Żądanie usunięcia można złożyć na adres kontaktowy; możliwość przyporządkowania losowych sesji może być ograniczona. Nie należy przekazywać haseł, kluczy ani danych karty. [Przed startem zapewnić dowód zgody, wersję informacji, procedurę żądań i dostępność pełnej polityki przed udzieleniem zgody.]

## 4. Retencja
Planowana polityka analityki: próbki zakładek do 30 dni kalendarzowych UTC; sesje do 30 dni od ostatniej obserwacji, z zachowaniem sesji potrzebnych do nieprzeterminowanych próbek; agregaty funkcji do 90 dni kalendarzowych UTC; pseudonimowe konta analityczne do 90 dni od ostatniej obserwacji, z wyjątkiem rekordów niezbędnych do odrębnego celu, w tym powiązanych limitów. Harmonogram retencji nie jest jeszcze aktywny. Retencja nie jest równoznaczna z usunięciem konta Google ani anulowaniem subskrypcji.
[Przed startem potwierdzić harmonogram, retencję dowodów zgody, logów, kopii zapasowych, wiadomości, limitów, rozliczeń i roszczeń. Dla każdego celu podać czas lub jasne kryterium.]

## 5. Odbiorcy i przekazywanie danych
W zależności od użytej funkcji dostawcy obejmują Google (logowanie), Streamlit/Snowflake (hosting), Neon (baza), Zoho (poczta), Stripe (płatności testowe; docelowo płatności) oraz GitHub (utrzymanie kodu i zadania techniczne). [Zweryfikować dokładne podmioty prawne, role administratora/podmiotu przetwarzającego, DPA, podwykonawców, rzeczywiste regiony i zakres danych; nie zakładać, że każdy dostawca ma dostęp do danych klientów.] 
Jeśli dane są przekazywane poza EOG, [opisać rzeczywiste państwa, podstawy transferu, decyzje adekwatności albo zabezpieczenia oraz sposób uzyskania ich kopii]. Linki informacyjne: https://policies.google.com/privacy, https://www.snowflake.com/legal/privacy-policy/, https://neon.com/privacy-policy, https://www.zoho.com/privacy.html, https://stripe.com/privacy, https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement. Polityki dostawców nie zastępują informacji Hoopzaro.

## 6. Cookies i technologie sesyjne
Logowanie Streamlit korzysta z mechanizmu identyfikacji sesji/cookie uwierzytelniającego; według dokumentacji standardowe cookie identyfikacji może wygasać po 30 dniach, a wylogowanie usuwa cookie aplikacji. Google może stosować własne cookies niezależnie. Niezbędne technologie mogą być używane w celu dostarczenia żądanej usługi. Opcjonalna analityka nie powinna uruchamiać się przed zgodą. [Sporządzić rzeczywisty wykaz cookies, pamięci przeglądarki, celów, czasów, stron trzecich i podstaw zgodnie z art. 399 PKE; sprawdzić faktyczne zachowanie przeglądarki i hostingu.]

## 7. Prawa
W zakresie przewidzianym w RODO przysługuje prawo dostępu, sprostowania, usunięcia, ograniczenia, przenoszenia danych, sprzeciwu wobec przetwarzania opartego na uzasadnionym interesie oraz wycofania zgody. Kontakt: contact@hoopzaro.com. W razie potrzeby poprosimy o proporcjonalne potwierdzenie tożsamości; nie zbieramy dodatkowych identyfikatorów wyłącznie po to, aby przypisywać anonimowe wizyty. Można złożyć skargę do właściwego organu nadzorczego, w Polsce do Prezesa UODO (https://uodo.gov.pl/). [Ustalić procedurę i odpowiedzialność za realizację żądań.]

## 8. Bezpieczeństwo i decyzje
Stosujemy kontrolę ról po stronie serwera, odrębne klucze i ograniczenia uprawnień, HTTPS oraz pseudonimizację telemetrii. [Zweryfikować środki, kopie i procedurę incydentów.] Prognozy dotyczą wydarzeń sportowych; nie są oceną osoby korzystającej z serwisu. [Potwierdzić brak decyzji wyłącznie zautomatyzowanych o skutkach prawnych lub podobnie istotnych i profilowania użytkowników; opisać ewentualne wyjątki.]

## 9. Dzieci, zmiany i kontakt
[Ustalić grupę wiekową, wymogi wieku i zasady zgody dzieci dla docelowych państw.] Przed uruchomieniem nowych celów przetwarzania lub zmianą zakresu analityki udostępnimy aktualne informacje i, gdy będzie to konieczne, poprosimy o nową zgodę. Data obowiązywania: [do uzupełnienia po zatwierdzeniu].

### Podstawy i materiały do weryfikacji (część robocza)
- RODO: art. 5–7, 8, 11–22, 28, 32–34, 44–49: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- EROD, wytyczne 05/2020 dotyczące zgody: https://www.edpb.europa.eu/documents/guideline/guidelines-052020-on-consent-under-regulation-2016679_pl
- Prawo komunikacji elektronicznej, art. 399: https://eli.sejm.gov.pl/eli/DU/2024/1221/ogl/pol
- Streamlit: https://docs.streamlit.io/develop/concepts/connections/authentication
