# Glowne podsumowanie strategii

Okres backtestu: **1954-07-02 - 2026-07-17**
Ostatni sygnal: **2026-07-17**

## Najwazniejsze wnioski
- Strategia konczy z CAGR **11.13%**, max drawdown **-26.98%** i wartoscia koncowa **2,003.49** z poczatkowych 1.00.
- Rekomendowany miks 30/70/0 ma CAGR **13.91%** przy max drawdown **-27.50%**; to domyslny kompromis miedzy strategia bazowa i srednio agresywna.
- Wariant srednio agresywny ma CAGR **15.06%** przy max drawdown **-32.20%**; uzywa tego samego filtra momentum, ale tylko do 180% ekspozycji.
- Wariant agresywny ma CAGR **19.94%** przy max drawdown **-52.89%**; to test, a nie domyslny wariant rebalancingu.
- 100% akcji ma podobny CAGR (**11.09%**), ale duzo glebszy max drawdown (**-54.61%**).
- Aktualnie strategia jest defensywna: akcje **31.12%**, obligacje/gotowka **68.88%**, zloto **0.00%**.
- W czesci obligacyjnej sygnal duration wynosi **50.00%**: to oznacza czesciowe, ale nie pelne, wejscie w obligacje stale.

## Wyniki
| Portfel | CAGR | Max DD | Zmiennosc | Sharpe | Wartosc koncowa |
|---|---:|---:|---:|---:|---:|
| Strategia | 11.13% | -26.98% | 9.57% | 1.16 | 2,003.49 |
| Rekomendowany miks 30/70/0 | 13.91% | -27.50% | 12.20% | 1.14 | 11,884.44 |
| Strategia srednio agresywna | 15.06% | -32.20% | 13.59% | 1.11 | 24,488.56 |
| Strategia agresywna | 19.94% | -52.89% | 21.73% | 0.92 | 490,360.39 |
| 100% akcje | 11.09% | -54.61% | 12.36% | 0.90 | 1,961.08 |
| 80/20 | 10.09% | -44.05% | 9.90% | 1.02 | 1,020.03 |
| 60/40 | 9.00% | -31.58% | 7.76% | 1.16 | 498.22 |

## Aktualna alokacja modelu
| Klasa | Udzial |
|---|---:|
| Akcje USA / SPX | 31.12% |
| Akcje swiat | 0.00% |
| Tech / NDX | 0.00% |
| Obligacje stale / 30+ | 34.44% |
| Obligacje zmienne / gotowka | 34.44% |
| Zloto | 0.00% |

## Praktyczny podzial do panelu rebalancingu
| Pozycja | Cel |
|---|---:|
| Akcje | 31.12% |
| Polskie obligacje nominalne | 34.44% |
| Polskie obligacje stale % | 8.61% |
| Polskie obligacje zmienne % | 8.61% |
| Zagraniczne obligacje stale % | 8.61% |
| Zagraniczne obligacje zmienne % | 8.61% |
| Zloto | 0.00% |

## Aktualne sygnaly makro
- Shiller: **80.00% akcji**
- Cykl Fed/bezrobocie/PKB: **0.00% akcji**
- Forward P/E: **13.37% akcji**
- CPI YoY: **3.23%**
- Real 10Y: **1.34%**
- GDP YoY: **0.64%**
- Forward P/E proxy: **42.61**

## Najwazniejsze raporty
- [Kapital i drawdown - skala liniowa](equity_curve_100.svg)
- [Kapital i drawdown - skala logarytmiczna](equity_curve_100_log.svg)
- [Alokacja akcji na tle S&P 500](allocation_percent.svg)
- [Obligacje stale/zmienne na tle makro](bond_allocation_macro.svg)
- [Fed Funds vs bezrobocie](rates_vs_unemployment.svg)
- [Histereza P/E](pe_hysteresis_path.svg)
- [Proporcja SPX vs NDX](spx_ndx_mix.svg)
- [Zloto](gold_allocation.svg)
- [Ropa jako filtr makro](oil_allocation.svg)
- [Aktywacja trybu lewarowanego](leverage_mode.svg)
- [Porownanie dekadowe](decade_comparison.html)
- [Czas pod woda](underwater_duration.html)
- [Lista transakcji i rebalancing](transactions_rebalancing.html)

## Jakosc danych
- high_1985_plus: 2168 tygodni
- medium_proxy_1971_1984: 731 tygodni
- medium_proxy_pre_1971: 861 tygodni

## Uwagi
- Forward P/E jest proxy bez look-ahead, nie oficjalna seria analityczna.
- Okres przed 1985 wykorzystuje wiecej proxy niz nowszy fragment backtestu.
- Wyniki przed startem ETF-ow sa czesciowo syntetyczne zgodnie z opisem w README.
- Koszt transakcyjny: 0.2% od kazdej strony transakcji kupna/sprzedazy.