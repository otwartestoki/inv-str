# Glowne podsumowanie strategii

Okres backtestu: **1954-07-02 - 1990-12-28**
Ostatni sygnal: **1990-12-28**

## Najwazniejsze wnioski
- Strategia konczy z CAGR **10.20%**, max drawdown **-26.98%** i wartoscia koncowa **34.65** z poczatkowych 1.00.
- Rekomendowany miks 30/70/0 ma CAGR **12.54%** przy max drawdown **-27.35%**; to domyslny kompromis miedzy strategia bazowa i srednio agresywna.
- Wariant srednio agresywny ma CAGR **13.54%** przy max drawdown **-27.50%**; uzywa tego samego filtra momentum, ale tylko do 180% ekspozycji.
- Wariant agresywny ma CAGR **18.01%** przy max drawdown **-27.50%**; to test, a nie domyslny wariant rebalancingu.
- 100% akcji ma podobny CAGR (**10.99%**), ale duzo glebszy max drawdown (**-39.16%**).
- Aktualnie strategia jest defensywna: akcje **55.00%**, obligacje/gotowka **45.00%**, zloto **0.00%**.
- W czesci obligacyjnej sygnal duration wynosi **50.00%**: to oznacza czesciowe, ale nie pelne, wejscie w obligacje stale.

## Wyniki
| Portfel | CAGR | Max DD | Zmiennosc | Sharpe | Wartosc koncowa |
|---|---:|---:|---:|---:|---:|
| Strategia | 10.20% | -26.98% | 6.10% | 1.67 | 34.65 |
| Rekomendowany miks 30/70/0 | 12.54% | -27.35% | 6.41% | 1.96 | 74.63 |
| Strategia srednio agresywna | 13.54% | -27.50% | 6.69% | 2.03 | 103.30 |
| Strategia agresywna | 18.01% | -27.50% | 8.53% | 2.11 | 421.89 |
| 100% akcje | 10.99% | -39.16% | 5.81% | 1.89 | 45.06 |
| 80/20 | 10.00% | -32.32% | 4.99% | 2.00 | 32.43 |
| 60/40 | 8.97% | -24.95% | 4.80% | 1.87 | 23.05 |

## Aktualna alokacja modelu
| Klasa | Udzial |
|---|---:|
| Akcje USA / SPX | 11.00% |
| Akcje swiat | 0.00% |
| Tech / NDX | 44.00% |
| Obligacje stale / 30+ | 22.50% |
| Obligacje zmienne / gotowka | 22.50% |
| Zloto | 0.00% |

## Praktyczny podzial do panelu rebalancingu
| Pozycja | Cel |
|---|---:|
| Akcje | 55.00% |
| Polskie obligacje nominalne | 22.50% |
| Polskie obligacje stale % | 5.62% |
| Polskie obligacje zmienne % | 5.62% |
| Zagraniczne obligacje stale % | 5.62% |
| Zagraniczne obligacje zmienne % | 5.62% |
| Zloto | 0.00% |

## Aktualne sygnaly makro
- Shiller: **80.00% akcji**
- Cykl Fed/bezrobocie/PKB: **80.00% akcji**
- Forward P/E: **86.07% akcji**
- CPI YoY: **6.25%**
- Real 10Y: **1.89%**
- GDP YoY: **0.60%**
- Forward P/E proxy: **13.35**

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
- high_1985_plus: 313 tygodni
- medium_proxy_1971_1984: 731 tygodni
- medium_proxy_pre_1971: 861 tygodni

## Uwagi
- Forward P/E jest proxy bez look-ahead, nie oficjalna seria analityczna.
- Okres przed 1985 wykorzystuje wiecej proxy niz nowszy fragment backtestu.
- Wyniki przed startem ETF-ow sa czesciowo syntetyczne zgodnie z opisem w README.
- Koszt transakcyjny: 0.2% od kazdej strony transakcji kupna/sprzedazy.