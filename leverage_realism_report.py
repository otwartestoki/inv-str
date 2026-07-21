from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_backtest import REPORTS, fred_csv, yahoo_adj_close


ROOT = Path(__file__).resolve().parent
OUT_HTML = REPORTS / "leverage_realism.html"
OUT_CSV = REPORTS / "leverage_realism_metrics.csv"
OUT_RETURNS = REPORTS / "leverage_realism_returns.csv"

ASSET_COLS = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
EQUITY_COLS = ["us_equity", "world_equity", "tech_equity"]
VARIANTS = {
    "strategy": "Bazowa",
    "strategy_recommended_mix": "Rekomendowany miks",
    "strategy_medium_aggressive": "Srednio agresywna",
    "strategy_aggressive": "Agresywna",
}
WEEKLY_COLS = {
    "strategy": "strategy",
    "strategy_recommended_mix": "strategy_recommended_mix",
    "strategy_medium_aggressive": "strategy_medium_aggressive",
    "strategy_aggressive": "strategy_aggressive",
}
PREFIXES = {
    "strategy": "w_",
    "strategy_medium_aggressive": "med_aggr_w_",
    "strategy_aggressive": "aggr_w_",
}


def perf(ret: pd.Series, periods_per_year: float) -> dict[str, float]:
    ret = ret.dropna()
    if ret.empty:
        return {"CAGR": np.nan, "Volatility": np.nan, "MaxDrawdown": np.nan, "FinalWealth": np.nan}
    wealth = (1.0 + ret).cumprod()
    years = len(ret) / periods_per_year
    cagr = wealth.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 and wealth.iloc[-1] > 0 else np.nan
    dd = wealth / wealth.cummax() - 1.0
    return {
        "CAGR": cagr,
        "Volatility": ret.std() * math.sqrt(periods_per_year),
        "MaxDrawdown": dd.min(),
        "FinalWealth": wealth.iloc[-1],
    }


def daily_returns() -> pd.DataFrame:
    prices = {
        "us_equity": yahoo_adj_close("SPY"),
        "world_equity": yahoo_adj_close("ACWI"),
        "tech_equity": yahoo_adj_close("QQQ"),
        "long_bond": yahoo_adj_close("TLT"),
        "gold": yahoo_adj_close("GLD"),
    }
    close = pd.DataFrame(prices).dropna(how="any")
    returns = close.pct_change().fillna(0.0)
    fed = fred_csv("FEDFUNDS").reindex(returns.index, method="ffill") / 100.0
    returns["floating_bond"] = fed.shift(1).fillna(fed) / 252.0
    # Fixed-bond sleeve is not central to the leverage test. TLT is a better daily proxy than
    # distributing weekly synthetic returns, but with lower duration than the 30+ sleeve.
    returns["fixed_bond"] = returns["long_bond"] * 0.45 + returns["floating_bond"] * 0.55
    returns["fed_funds"] = fed
    return returns


def daily_weights(weekly: pd.DataFrame, daily_index: pd.DatetimeIndex, variant: str) -> pd.DataFrame:
    if variant == "strategy_recommended_mix":
        base = daily_weights(weekly, daily_index, "strategy")
        medium = daily_weights(weekly, daily_index, "strategy_medium_aggressive")
        return 0.30 * base + 0.70 * medium
    prefix = PREFIXES[variant]
    cols = [prefix + col for col in ASSET_COLS]
    weights = weekly[cols].copy()
    weights.columns = ASSET_COLS
    return weights.reindex(daily_index, method="ffill").shift(1).bfill()


def realistic_return(
    weights: pd.DataFrame,
    ret: pd.DataFrame,
    financing_spread: float,
    product_drag: float,
    tracking_drag: float,
) -> pd.Series:
    gross = (weights[ASSET_COLS] * ret[ASSET_COLS]).sum(axis=1)
    gross_exposure = weights[ASSET_COLS].sum(axis=1)
    equity_exposure = weights[EQUITY_COLS].sum(axis=1)
    leverage_excess = (gross_exposure - 1.0).clip(lower=0.0)
    financing = leverage_excess * ((ret["fed_funds"].fillna(0.0) + financing_spread) / 252.0)
    # Daily-reset ETF cost assumption: expense/swap/tracking drag on the levered equity sleeve.
    product_cost = equity_exposure.clip(lower=1.0).sub(1.0).clip(lower=0.0) * ((product_drag + tracking_drag) / 252.0)
    daily = gross - financing - product_cost
    return daily.clip(lower=-0.99)


def write_html(metrics: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> None:
    def pct(value: float) -> str:
        return "" if pd.isna(value) else f"{value * 100:.2f}%"

    def num(value: float) -> str:
        return "" if pd.isna(value) else f"{value:,.2f}"

    rows = []
    for _, row in metrics.iterrows():
        cls = "warn" if row["model"] == "Dzienny reset konserwatywny" else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(row['variant_label'])}</td>"
            f"<td class=\"{cls}\">{html.escape(row['model'])}</td>"
            f"<td>{pct(row['CAGR'])}</td>"
            f"<td>{pct(row['Volatility'])}</td>"
            f"<td>{pct(row['MaxDrawdown'])}</td>"
            f"<td>{num(row['FinalWealth'])}</td>"
            f"<td>{pct(row['CAGR_gap_vs_weekly'])}</td>"
            "</tr>"
        )

    note = """
      <p><strong>Interpretacja:</strong> ten raport nie probuje udowodnic, ze lewar jest dobry albo zly.
      Pokazuje, jak bardzo wynik wariantow lewarowanych zalezy od sposobu liczenia. Model tygodniowy mnozy
      tygodniowa stope zwrotu przez ekspozycje, natomiast model dzienny sklada codzienne ruchy indeksow,
      odejmuje koszt finansowania i koszt produktu lewarowanego. To jest uczciwsze dla ETF-ow 2x/3x.</p>
    """
    html_text = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wiarygodnosc backtestu lewarowanego</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; color: #243033; background: #f6f3ee; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    a {{ color: #0b5cad; }}
    .panel {{ background: #fff; border: 1px solid #ddd4c7; border-radius: 8px; padding: 16px; margin: 14px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border-bottom: 1px solid #e7e1d8; padding: 8px 9px; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ background: #f1ece4; }}
    .warn {{ color: #8a3b00; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: #6b6258; font-size: 13px; }}
  </style>
</head>
<body>
<main>
  <nav><a href="../report_view.html">Backtest strategii</a> / Wiarygodnosc lewara</nav>
  <h1>Wiarygodnosc backtestu strategii lewarowanych</h1>
  <p>Okres dziennej analizy: <strong>{start.date()} - {end.date()}</strong>. Zakres zaczyna sie dopiero wtedy,
  gdy dostepne sa realne dzienne dane ETF dla SPY, QQQ, ACWI, TLT i GLD.</p>
  <section class="panel">{note}</section>
  <section class="panel">
    <h2>Porownanie metryk</h2>
    <p><a href="leverage_realism_metrics.csv">CSV metryk</a> / <a href="leverage_realism_returns.csv">CSV dziennych zwrotow</a></p>
    <table>
      <thead><tr><th>Wariant</th><th>Model</th><th>CAGR</th><th>Zmiennosc</th><th>Max DD</th><th>Kapital koncowy</th><th>Roznica CAGR vs tyg.</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Zalozenia modelu dziennego</h2>
    <ul>
      <li>Wagi strategii sa brane z tygodniowego modelu, ale zwroty akcji i ETF-ow sa skladane dziennie.</li>
      <li>Model bazowy dzienny: koszt finansowania = Fed Funds + 1,5 p.p.; koszt produktu/tracking = 1,25% rocznie na nadwyzce ekspozycji akcyjnej ponad 100%.</li>
      <li>Model konserwatywny: koszt finansowania = Fed Funds + 2,5 p.p.; koszt produktu/tracking = 2,5% rocznie na nadwyzce ekspozycji akcyjnej ponad 100%.</li>
      <li>Wyniki przed 2008 rokiem nie sa tu pokazywane, bo wymagaloby to syntetycznego ACWI/GLD/TLT i znowu obnizaloby wiarygodnosc.</li>
    </ul>
  </section>
</main>
</body>
</html>
"""
    OUT_HTML.write_text(html_text, encoding="utf-8")


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    weekly = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    weekly_returns = pd.read_csv(REPORTS / "returns.csv", parse_dates=["date"]).set_index("date")
    daily = daily_returns()
    start = max(daily.index.min(), weekly.index.min())
    end = min(daily.index.max(), weekly.index.max())
    daily = daily.loc[start:end]
    weekly_returns = weekly_returns.loc[start:end]
    rows: list[dict[str, float | str]] = []
    out_returns = pd.DataFrame(index=daily.index)

    for variant, label in VARIANTS.items():
        weekly_ret = weekly_returns[WEEKLY_COLS[variant]].dropna()
        weekly_perf = perf(weekly_ret, 52.1775)
        rows.append({"variant": variant, "variant_label": label, "model": "Tygodniowy obecny", **weekly_perf, "CAGR_gap_vs_weekly": 0.0})

        weights = daily_weights(weekly, daily.index, variant)
        base_daily = realistic_return(weights, daily, financing_spread=0.015, product_drag=0.0095, tracking_drag=0.0030)
        conservative_daily = realistic_return(weights, daily, financing_spread=0.025, product_drag=0.0150, tracking_drag=0.0100)
        out_returns[f"{variant}_daily_reset_base"] = base_daily
        out_returns[f"{variant}_daily_reset_conservative"] = conservative_daily

        for model, ret in [
            ("Dzienny reset bazowy", base_daily),
            ("Dzienny reset konserwatywny", conservative_daily),
        ]:
            daily_perf = perf(ret, 252.0)
            rows.append(
                {
                    "variant": variant,
                    "variant_label": label,
                    "model": model,
                    **daily_perf,
                    "CAGR_gap_vs_weekly": daily_perf["CAGR"] - weekly_perf["CAGR"],
                }
            )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT_CSV, index=False, float_format="%.8f")
    out_returns.to_csv(OUT_RETURNS, index_label="date", float_format="%.10f")
    write_html(metrics, start, end)
    print(OUT_HTML.resolve())


if __name__ == "__main__":
    main()
