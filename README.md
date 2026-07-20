# inv-str

Backtest tygodniowej strategii alokacji portfela opartej o trzy glowne podstrategie:

1. Shiller CAPE momentum.
2. Cykl makro: Fed Funds, bezrobocie, inflacja, realne PKB.
3. Forward P/E S&P 500 z petla histerezy.

Strategia laczy te trzy sygnaly przez srednia arytmetyczna udzialu akcji. Nastepnie decyduje, jak podzielic czesc akcyjna miedzy SPX i NDX oraz jak podzielic czesc defensywna miedzy obligacje/gotowke i zloto.

To jest eksperyment badawczy, nie porada inwestycyjna.

## Uruchomienie

Najprosciej odswiezyc wszystko jednym plikiem:

```powershell
.\refresh_reports.bat
```

Ten plik przelicza backtest, wykresy, tabele roczne oraz liste rebalancingow.

Na Linuxie, macOS i w GitHub Actions uzywany jest odpowiednik:

```bash
bash refresh_reports.sh
```

```powershell
python .\strategy_backtest.py
python .\allocation_plot.py
python .\rates_unemployment_plot.py
python .\pe_hysteresis_plot.py
python .\spx_ndx_mix_plot.py
python .\gold_allocation_plot.py
python .\oil_allocation_plot.py
python .\bond_allocation_plot.py
python .\yearly_allocation_report.py
python .\annual_heatmap_report.py
python .\decade_report.py
python .\underwater_report.py
python .\transaction_report.py
python .\bond_switch_report.py
```

Najwygodniejszy podglad:

```text
index.html
```

Panel glowny prowadzi do backtestu, importera historii portfela, rebalancingu oraz planowania budzetu. Sam backtest jest nadal dostepny tutaj:

```text
report_view.html
```

Panel rebalancingu strategii:

```text
rebalance_strategy.html
```

Importer historii portfela:

```text
portfolio_import.html
```

Planowanie budzetu:

```text
budget_planning.html
```

Importer dziala lokalnie w przegladarce. Zapamietuje scalona historie w `localStorage`, wiec po zaladowaniu nowych CSV/XLS dopisuje tylko nowe rekordy i nie powinien dublowac juz wczytanych operacji. Klasyfikacja ma dwie osie:

- typ operacji: wplata, wyplata, zakup, sprzedaz, dywidenda/odsetki, stan pozycji, przeksiegowanie ignorowane, oplata/podatek, korekta,
- rodzaj waloru: akcje USA/SPX, akcje swiat, tech/NDX, obligacje 30+, floating/gotowka, zloto, do klasyfikacji.

## Publikacja w internecie

Projekt jest przygotowany pod GitHub Pages + GitHub Actions.

1. Utworz repozytorium na GitHubie i wypchnij do niego ten katalog.
2. W repozytorium wejdz w `Settings` -> `Pages`.
3. W `Build and deployment` ustaw `Source` na `GitHub Actions`.
4. Wejdz w `Actions` i uruchom workflow `Refresh reports and publish Pages` przyciskiem `Run workflow`.

Workflow:

- instaluje zaleznosci z `requirements.txt`,
- uruchamia `refresh_reports.sh`,
- buduje statyczna paczke z `index.html`, `report_view.html`, `portfolio_import.html`, `rebalance_strategy.html`, `budget_planning.html`, `README.md`, `assets/`, `reports/` i `data/processed/`,
- publikuje ja jako GitHub Pages.

Domyslnie raport odswieza sie automatycznie w soboty o `06:25 UTC`. Mozna tez wymusic odswiezenie recznie w zakladce `Actions`.

Po pierwszym udanym wdrozeniu strona bedzie dostepna pod adresem podobnym do:

```text
https://twoj-login.github.io/nazwa-repozytorium/
```

## Dane

Backtest dziala na tygodniowej osi czasu od 1954 roku. Dane dzienne sa agregowane do tygodni, a dane miesieczne i kwartalne sa przenoszone metoda ostatniego znanego odczytu.

Zrodla:

- Robert Shiller / Yale: miesieczne dane S&P 500, dywidendy, zyski, CPI i CAPE.
- FRED: Fed Funds, bezrobocie, CPI, realny PKB, rentownosci 10Y.
- Yahoo Finance chart API: realne serie adjusted close dla ETF/funduszy, gdy istnieja.

Proxy i symulacje:

- Przed startem ETF-ow uzywany jest S&P 500 total return z danych Shillera jako proxy akcji USA.
- NDX/technologia przed dostepna historia QQQ jest symulowana jako bardziej zmienna wersja akcji USA.
- Przed dostepna historia DGS10 rentownosc 10Y jest uzupelniana seria `long_rate` z danych Shillera.
- Obligacje stale oprocentowane sa symulowane z rentownosci 10Y: carry minus duration razy zmiana rentownosci.
- Obligacje zmiennoprocentowe/gotowka sa symulowane stopa Fed Funds.
- Forward P/E jest proxy bez look-ahead: cena S&P 500 / estymowany EPS 12M, oparty o ostatni EPS i trend wzrostu zyskow.
- Zloto jest aktywowane od okresu z realna historia GLD w danych albo z lokalnego pliku `data/raw/gold_price.csv`, jesli taki plik zostanie dodany. Plik powinien miec kolumne `date` oraz jedna z kolumn `price`, `gold` albo `close`. Opcjonalnie mozna tez ustawic zmienna srodowiskowa `FRED_GOLD_SERIES_ID` na poprawny identyfikator serii FRED z cena zlota.

Jakosc danych w pelnym panelu:

- `medium_proxy_pre_1971` - najstarszy okres, bez realnych ETF-ow i bez swobodnie handlowanego zlota w modelu.
- `medium_proxy_1971_1984` - lepszy reżim makro, ale nadal bez realnych ETF-ow dla wiekszosci aktywow.
- `high_1985_plus` - glowny okres porownawczy z bardziej wiarygodnymi danymi rynkowymi i makro.

## Modul 1: Shiller CAPE momentum

Strategia liczy:

- miesieczny Shiller CAPE,
- roznice CAPE wzgledem 24 miesiecy wczesniej,
- 2-miesieczna srednia ruchoma tej roznicy.

Regula:

- jesli wartosc spada ponizej `-6`, modul Shillera daje `20%` akcji,
- w przeciwnym razie daje `80%` akcji.

Ten modul ma rozpoznawac momenty, gdy wyceny i sentyment mocno sie pogorszyly i rynek staje sie atrakcyjniejszy.

## Modul 2: cykl makro Fed Funds / bezrobocie

Glowny sygnal wyjscia z akcji:

- Fed Funds przecina bezrobocie od gory,
- stopy spadaja,
- bezrobocie rosnie.

Po takim sygnale modul cyklu ustawia `0%` akcji. To jest mocny tryb defensywny.

Powrot z defensywy:

- defensywa trwa co najmniej rok,
- glownym sygnalem powrotu jest ujemna dynamika realnego PKB wzgledem poprzedniego odczytu (`gdp_mom < 0`),
- po takim sygnale modul cyklu wraca do `80%` akcji przez 6 miesiecy w 6 transzach,
- jesli recesja nie przychodzi, modul moze rozpoznac scenariusz soft landing / falszywy alarm i rowniez wrocic przez 6 transz,
- jesli sygnal PKB nie wystapi, powrot moze uruchomic modul Shillera jako fallback, ale tylko przy potwierdzonym stresie makro/rynkowym:
  - PKB YoY < `1%`,
  - albo bezrobocie wzroslo o co najmniej `0.75 p.p.` w 26 tygodni,
  - albo S&P 500 jest co najmniej `15%` ponizej szczytu.

Dodatkowy tryb risk-on:

- jesli gospodarka jest w potwierdzonej ekspansji, strategia moze podniesc bazowy udzial akcji do `90%`,
- warunki ekspansji to dodatnie PKB YoY, nieujemne PKB MoM, brak wzrostu bezrobocia, CPI YoY ponizej `4%`, brak agresywnego wzrostu Fed Funds oraz brak rezimu inflacyjnego zaciesniania,
- ten tryb dziala tylko wtedy, gdy modul Shillera i modul cyklu sa jednoczesnie risk-on.

Warunek soft landing / falszywego alarmu:

- po minimum roku defensywy,
- przez co najmniej `13 tygodni` gospodarka jest w ekspansji:
  - PKB YoY > `2%`,
  - `gdp_mom >= 0`,
  - bezrobocie nie rosnie w horyzoncie 26 tygodni,
  - CPI YoY < `3.5%`,
  - Fed nie podnosi agresywnie, czyli zmiana Fed Funds w 26 tygodni <= `0.75 p.p.`,
  - S&P 500 jest powyzej sredniej 40-tygodniowej albo drawdown jest mniejszy niz `10%`,
  - nie trwa rezim inflacyjnego zaciesniania.

Ten warunek ma wygaszac defensywe po falszywym sygnale recesyjnym. To pozwala strategii uczestniczyc w hossie typu soft landing, zamiast czekac tylko na recesyjny sygnal powrotu.

W praktyce przecięcie stop procentowych i bezrobocia jest traktowane jako sygnal wyjscia z akcji, nie wejscia.

## Modul 3: Forward P/E z histereza

Modul P/E wyznacza udzial akcji/obligacji liniowo, ale z petla histerezy. Linie sa rownolegle.

Gdy P/E rosnie:

- `P/E 20 -> 90% akcji`,
- `P/E 37 -> 10% akcji`,
- pomiedzy tymi punktami zaleznosc jest liniowa.

Gdy P/E spada:

- `P/E 10 -> 90% akcji`,
- `P/E 27 -> 10% akcji`,
- pomiedzy tymi punktami zaleznosc jest liniowa.

Przelaczenie galezi odbywa sie tylko na krancach petli:

- po dojściu do wysokiego P/E strategia przechodzi na galaz spadkowa,
- po dojściu do niskiego P/E strategia wraca na galaz wzrostowa.

Podstrategia P/E zmienia swoja alokacje dopiero, gdy zmiana przekracza `5 p.p.`

Wyjatek po sygnale powrotu z PKB:

- przez 12 miesiecy po `gdp_mom < 0` modul P/E ma floor `40%` akcji,
- ma to ograniczyc sytuacje, w ktorej spadek zyskow w recesji sztucznie blokuje wejscie w akcje.

## Laczenie sygnalow

Docelowy udzial akcji jest liczony jako srednia z trzech podstrategii:

```text
target_equity = mean(shiller_equity, cycle_equity, pe_equity)
```

To jest blizsze pierwotnemu zalozeniu strategii: P/E ma byc rownym glosem, a nie tylko szerokim sufitem. Dzieki temu strategia nie przykleja sie automatycznie do portfela `80/20`, gdy Shiller i cykl sa risk-on.

Osobno dzialaja limity makro. W potwierdzonej ekspansji strategia moze podniesc udzial akcji do `90%`, ale w rezimach inflacyjnych maksymalna ekspozycja jest ograniczana:

```text
target_equity = min(target_equity, macro_cap)
```

Wyjatek dla reĹĽimu inflacyjnego zaciesniania:

- CPI YoY > `4%`,
- Fed Funds rosnie o ponad `0.75 p.p.` w 26 tygodni,
- rentownosc 10Y rosnie o ponad `0.50 p.p.` w 26 tygodni.

W takim rezimie spadek P/E nie jest traktowany jak pelny sygnal okazji, bo rosna stopy dyskontowe. `macro_cap` jest wtedy ograniczony do maksymalnie `65%` akcji.

Przyklad:

```text
Shiller = 80%
Cykl = 0%
P/E = 57%

target_equity = 46%
```

## SPX vs NDX w czesci akcyjnej

Czesc akcyjna nie zawsze trafia tylko do SPX. Po mocnym wejściu w akcje strategia najpierw kupuje mocniej NDX, a potem przechodzi do SPX w zaleznosci od makro.

Mocne wejscie w akcje:

- docelowa ekspozycja na akcje rosnie o co najmniej `15 p.p.`,
- albo modul cyklu wraca z defensywy do risk-on,
- albo zaczyna sie rampa powrotu z defensywy.

Rezim inflacyjnego zaciesniania blokuje NDX-heavy. W takim otoczeniu czesc akcyjna pozostaje w SPX, dopoki inflacja, Fed i rentownosci 10Y nie przestana razem naciskac na wyceny.

Przed 1985 rokiem NDX jest tylko proxy, dlatego strategia ogranicza jego wage w czesci akcyjnej:

- early recovery: maksymalnie `30%` czesci akcyjnej w syntetycznym NDX,
- mid recovery: maksymalnie `20%`,
- late cycle: `0%`.

Etapy:

1. Early recovery:
   - `80%` czesci akcyjnej w NDX,
   - `20%` czesci akcyjnej w SPX.

2. Mid recovery:
   - `50%` NDX,
   - `50%` SPX.

3. Late cycle:
   - `0%` NDX,
   - `100%` SPX.

Przejscie z NDX-heavy do 50/50 nastepuje tylko przy poprawie makro:

- PKB YoY jest dodatnie,
- dynamika PKB poprawia sie wzgledem 26 tygodni wczesniej,
- bezrobocie nie rosnie wzgledem 26 tygodni wczesniej.

Zamkniecie NDX i przejscie do samego SPX nastepuje przy sygnalach zaciesniania/przegrzania:

- Fed Funds wzrosly o ponad `0.50 p.p.` w 26 tygodni,
- albo CPI YoY > `3.5%` i Fed Funds rosna.
- albo Shiller przechodzi risk-off,
- albo P/E jest wysokie, a modul P/E redukuje udzial akcji.

Nie ma awaryjnych przejsc po liczbie tygodni. Decyduja wskazniki makro.

## Zloto

Zloto jest pozycja na rezim inflacyjno-monetarnej niepewnosci.

Aktywny sygnal ropy:

- pierwsza podwyzka stop po okresie bardzo niskich stop.
- rezim stagflacyjny, jesli zloto jest dostepne w danych.

Trzymanie:

- minimum `2 lata`,
- brak krotkiego, nerwowego wyjscia,
- zloto moze byc trzymane wiele lat, jesli rezim makro nadal temu sprzyja.

Sprzedaz:

- inflacja jest opanowana,
- realne stopy sa dodatnie,
- Fed nie podnosi agresywnie,
- Shiller pozwala wracac do akcji.

Maksymalny udzial zlota w portfelu to `10%`.

W rezimie stagflacyjnym maksymalny udzial zlota rosnie do `15%`, ale tylko dla okresu, w ktorym strategia ma realna lub lokalnie dostarczona serie zlota.

Rezim stagflacyjny:

- CPI YoY > `6%`,
- oraz PKB YoY < `1%` albo bezrobocie rosnie w ostatnich 26 tygodniach.

Gdy taki rezim wystepuje, strategia ogranicza calkowita ekspozycje na akcje do `55%`. Nadwyzka trafia do czesci defensywnej, czyli do floating/gotowki, obligacji 30+ wedlug scoringu duration oraz zlota, jesli jego sygnal jest aktywny.

Strategia ogranicza tez agresywne przejscie w obligacje 30+ przed szczytem inflacji.

## Ropa / surowce

Ropa nie jest aktywem w portfelu. Jest filtrem makro dla szoku energetycznego.

Dane:

- strategia uzywa WTI spot z FRED jako proxy rezimu energetycznego,
- opcjonalnie mozna podac lokalny plik `data/raw/oil_price.csv` z kolumnami `date` oraz `price`, `oil` albo `close`.

Aktywny sygnal ropy:

- cena ropy jest powyzej 40-tygodniowej sredniej,
- 26-tygodniowe momentum ropy jest powyzej `10%`,
- CPI YoY > `3.5%`,
- bezrobocie nie rosnie mocno,
- brak popytowego ryzyka recesji: PKB YoY nie jest ujemne i bezrobocie nie wzroslo o ponad `0.75 p.p.` w 26 tygodni.

Dzialanie sygnalu:

- strategia nie kupuje ropy,
- przy aktywnym `oil_regime` ogranicza obligacje 30+ do maksymalnie `25%` czesci defensywnej,
- nadwyzka trafia do floating/gotowki.

Wygaszenie sygnalu:

- ropa traci trend,
- momentum wygasa,
- inflacja przestaje potwierdzac rezim,
- albo pojawia sie ryzyko popytowej recesji.

## Obligacje

Czesc defensywna trafia do:

- obligacji/gotowki zmiennoprocentowej, gdy nie ma sygnalu obligacji stalych,
- obligacji dlugoterminowych 30+ (`long_bond` / TLT), gdy stopy nominalne lub rentownosc 10Y sa wysokie,
- czesciowego duration trade, gdy Fed nadal jest wysoko, ale nie podnosi juz agresywnie,
- mocniejszego duration trade, gdy wysokie stopy lacza sie z pauza Fed, spadkiem rentownosci albo inflacja po szczycie.

Udzial obligacji 30+ nie jest przelacznikiem 0/1. Strategia skaluje czesc obligacyjna miedzy zmiennoprocentowe/gotowke i obligacje 30+ przez `long_bond_share`.

`long_bond_share` jest oparty o prosty scoring rezimu stóp:

- wysokie stopy nominalne,
- bardzo wysokie stopy albo wysokie realne rentownosci,
- Fed przestaje podnosic albo zaczyna obnizac,
- inflacja jest po szczycie,
- rentownosci 10Y zaczynaja spadac.

Punkty odejmowane sa, gdy Fed dalej agresywnie podnosi, inflacja przyspiesza albo rentownosci 10Y szybko rosna bez potwierdzenia spadku inflacji.

W rezimie inflacyjnego zaciesniania strategia ogranicza tez agresywne wejscie w obligacje 30+, dopoki inflacja nie jest wyraznie po szczycie. Wtedy wieksza czesc defensywna pozostaje w obligacjach zmiennoprocentowych/gotowce.

W rezimie stagflacyjnym punktacja obligacji 30+ jest obnizana, dopoki inflacja nie jest po szczycie. Chodzi o to, zeby nie kupowac zbyt wczesnie dlugiego duration, gdy Fed nadal walczy z inflacja i rentownosci moga jeszcze rosnac.

Ograniczenie ryzyka:

- gdy Fed dalej agresywnie podnosi stopy i inflacja ponownie przyspiesza, udzial 30+ jest ograniczany,
- gdy rentownosc 10Y skacze szybko w gore bez potwierdzenia spadku inflacji, udzial 30+ jest ograniczany.

## Rebalancing

Portfel liczy docelowe wagi co tydzien, ale faktycznie zmienia alokacje dopiero, gdy ktorykolwiek skladnik roznicuje sie od trzymanej wagi o co najmniej `5 p.p.`

To ogranicza drobne korekty i nadmierny turnover.

Wyjatek:

- podczas 6-miesiecznej rampy powrotu z defensywy rebalancing wykonuje kazda transze,
- wtedy prog `5 p.p.` jest czasowo zawieszony, zeby nie opozniac wejscia w akcje.

Koszt transakcyjny w backtescie:

- `0.2%` od kazdej strony transakcji kupna/sprzedazy,
- koszt jest liczony od obrotu wynikajacego ze zmian wag portfela.

## Benchmarki

Strategia jest porownywana z:

- `100% akcje`: 100% akcje USA,
- `60/40`: 60% akcje USA, 40% obligacje stale,
- `80/20`: 80% akcje USA, 20% obligacje stale.

## Raporty

Glowne pliki w katalogu `reports`:

- `summary.md` - glowne podsumowanie.
- `weekly_backtest.csv` - pelny tygodniowy panel z sygnalami, wagami i stopami zwrotu.
- `metrics.csv` - CAGR, zmiennosc, Sharpe, max drawdown, final wealth.
- `equity_curve_100.svg` - wzrost inwestycji 100 USD i drawdown.
- `equity_curve_100_log.svg` - wzrost inwestycji 100 USD w skali logarytmicznej i drawdown.
- `annual_heatmap.html` - heatmapa rocznych stop zwrotu i rocznych max drawdown.
- `decade_comparison.html` - porownanie dekadowe strategii i benchmarkow.
- `underwater_duration.html` - analiza czasu na stracie wzgledem poprzedniego ATH.
- `allocation_percent.svg` - udzial akcji strategii i benchmarkow na tle SPX.
- `rates_vs_unemployment.svg` - Fed Funds vs bezrobocie na tle SPX.
- `pe_hysteresis_path.svg` - sciezka po petli histerezy P/E.
- `spx_ndx_mix.svg` - jedna linia 0-100% pokazujaca udzial NDX w czesci akcyjnej.
- `gold_allocation.svg` - udzial zlota na tle ceny zlota.
- `oil_allocation.svg` - sygnal ropy na tle ceny WTI i aktywnych rezimow surowcowych.
- `bond_allocation_macro.svg` - jedna linia 0-100% pokazujaca udzial obligacji 30+ w czesci defensywnej.
- `yearly_allocation_mix.html` - roczne proporcje akcje/obligacje dla strategii i benchmarkow.
- `transactions_rebalancing.html` - lista rebalancingow i transakcji wynikajacych ze zmian wag.
- `bond_switches.html` - daty przejsc miedzy obligacjami staloprocentowymi i zmiennoprocentowymi/gotowka.
- `report_view.html` - zbiorczy lokalny podglad raportow.

## Obecny charakter strategii

Strategia jest defensywna, ale nie pasywna:

- wychodzi mocno z akcji po sygnale Fed Funds / bezrobocie,
- wraca do akcji po ujemnym PKB MoM, potwierdzeniu Shillera albo sygnale soft landing,
- w potwierdzonej ekspansji moze podniesc udzial akcji do `90%`,
- po wejściu w akcje preferuje NDX w pierwszej fazie odbicia,
- przed 1985 ogranicza syntetyczny NDX, zeby nie opierac wyniku na zbyt agresywnym proxy,
- pozniej przechodzi do SPX wraz z dojrzewaniem cyklu,
- trzyma zloto w rezimach inflacyjno-monetarnych i stagflacyjnych, jesli ma dostepna serie zlota,
- rebalansuje tylko przy zmianach co najmniej `5 p.p.`
