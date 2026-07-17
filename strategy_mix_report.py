from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
STRATEGIES = ["strategy", "strategy_medium_aggressive", "strategy_aggressive"]
LABELS = {
    "strategy": "Bazowa",
    "strategy_medium_aggressive": "Srednio agresywna",
    "strategy_aggressive": "Agresywna",
}


def pct(value: float) -> str:
    return f"{value:.1%}"


def metric_row(name: str, ret: pd.Series, weights: tuple[float, float, float]) -> dict[str, float | str]:
    ret = ret.dropna()
    wealth = (1.0 + ret).cumprod()
    years = len(ret) / 52.1775
    cagr = wealth.iloc[-1] ** (1.0 / years) - 1.0
    volatility = ret.std() * math.sqrt(52.1775)
    drawdown = wealth / wealth.cummax() - 1.0
    sharpe = cagr / volatility if volatility > 0 else float("nan")
    return {
        "name": name,
        "base_weight": weights[0],
        "medium_weight": weights[1],
        "aggressive_weight": weights[2],
        "cagr": cagr,
        "max_drawdown": drawdown.min(),
        "volatility": volatility,
        "sharpe_0rf": sharpe,
        "final_wealth": wealth.iloc[-1],
        "return_to_dd": cagr / abs(drawdown.min()) if drawdown.min() < 0 else float("nan"),
    }


def mix_name(base: float, medium: float, aggressive: float) -> str:
    return f"{base:.0%} / {medium:.0%} / {aggressive:.0%}"


def color(value: float, low: float, high: float, invert: bool = False) -> str:
    if high <= low:
        return "#f7f5ef"
    t = max(0.0, min(1.0, (value - low) / (high - low)))
    if invert:
        t = 1.0 - t
    if t >= 0.5:
        k = (t - 0.5) * 2.0
        r = int(247 + (79 - 247) * k)
        g = int(245 + (151 - 245) * k)
        b = int(239 + (112 - 239) * k)
    else:
        k = t * 2.0
        r = int(198 + (247 - 198) * k)
        g = int(77 + (245 - 77) * k)
        b = int(82 + (239 - 82) * k)
    return f"rgb({r},{g},{b})"


def metric_table(data: pd.DataFrame) -> str:
    ordered = data.sort_values(["return_to_dd", "cagr"], ascending=[False, False])
    rows = []
    cagr_low, cagr_high = ordered["cagr"].min(), ordered["cagr"].max()
    dd_low, dd_high = ordered["max_drawdown"].abs().min(), ordered["max_drawdown"].abs().max()
    sharpe_low, sharpe_high = ordered["sharpe_0rf"].min(), ordered["sharpe_0rf"].max()
    for _, row in ordered.iterrows():
        rows.append(
            "<tr>"
            f"<td>{row['name']}</td>"
            f"<td>{pct(row['base_weight'])}</td>"
            f"<td>{pct(row['medium_weight'])}</td>"
            f"<td>{pct(row['aggressive_weight'])}</td>"
            f"<td style=\"background:{color(row['cagr'], cagr_low, cagr_high)}\">{pct(row['cagr'])}</td>"
            f"<td style=\"background:{color(abs(row['max_drawdown']), dd_low, dd_high, invert=True)}\">{pct(row['max_drawdown'])}</td>"
            f"<td>{pct(row['volatility'])}</td>"
            f"<td style=\"background:{color(row['sharpe_0rf'], sharpe_low, sharpe_high)}\">{row['sharpe_0rf']:.2f}</td>"
            f"<td>{row['return_to_dd']:.2f}</td>"
            f"<td>{row['final_wealth']:,.0f}x</td>"
            "</tr>"
        )
    return "".join(rows)


def write_html(data: pd.DataFrame) -> None:
    best_compromise = data.sort_values(["return_to_dd", "cagr"], ascending=[False, False]).iloc[0]
    best_cagr = data.sort_values("cagr", ascending=False).iloc[0]
    best_dd = data.sort_values("max_drawdown", ascending=False).iloc[0]
    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Miksy wariantow strategii</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    p {{ margin: 0 0 18px; color: #555; line-height: 1.45; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin: 20px 0; }}
    .card {{ background: #fff; border: 1px solid #ddd8cc; padding: 14px; }}
    .card span {{ display: block; color: #666; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .card strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; border-right: 1px solid #eee8dc; text-align: right; font-size: 13px; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; }}
    tr:hover td {{ background: #f7f5ef !important; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Miksy wariantow strategii</h1>
    <p>Test staloprocentowych miksow: strategia bazowa / srednio agresywna / agresywna. Kazdy mix jest rebalansowany tygodniowo do zadanych proporcji. <a href="strategy_mix_metrics.csv">CSV metryk</a> / <a href="strategy_mix_returns.csv">CSV zwrotow</a></p>
    <div class="cards">
      <div class="card"><span>Najlepszy kompromis CAGR/DD</span><strong>{best_compromise['name']}</strong><p>CAGR {pct(best_compromise['cagr'])}, DD {pct(best_compromise['max_drawdown'])}</p></div>
      <div class="card"><span>Najwyzszy CAGR</span><strong>{best_cagr['name']}</strong><p>CAGR {pct(best_cagr['cagr'])}, DD {pct(best_cagr['max_drawdown'])}</p></div>
      <div class="card"><span>Najmniejszy DD</span><strong>{best_dd['name']}</strong><p>CAGR {pct(best_dd['cagr'])}, DD {pct(best_dd['max_drawdown'])}</p></div>
    </div>
    <h2>Ranking miksow</h2>
    <table>
      <thead>
        <tr>
          <th>Mix bazowa / srednia / agresywna</th>
          <th>Bazowa</th>
          <th>Srednia</th>
          <th>Agresywna</th>
          <th>CAGR</th>
          <th>Max DD</th>
          <th>Zmiennosc</th>
          <th>Sharpe</th>
          <th>CAGR/DD</th>
          <th>Koncowa wartosc</th>
        </tr>
      </thead>
      <tbody>{metric_table(data)}</tbody>
    </table>
  </main>
</body>
</html>
"""
    (REPORTS / "strategy_mix_report.html").write_text(html, encoding="utf-8")


def main() -> None:
    returns = pd.read_csv(REPORTS / "returns.csv", parse_dates=["date"]).set_index("date")
    base_returns = returns[STRATEGIES]
    mix_returns = {}
    rows = []

    for base_pct in range(0, 101, 10):
        for medium_pct in range(0, 101 - base_pct, 10):
            aggressive_pct = 100 - base_pct - medium_pct
            weights = (base_pct / 100.0, medium_pct / 100.0, aggressive_pct / 100.0)
            name = mix_name(*weights)
            ret = (
                weights[0] * base_returns["strategy"]
                + weights[1] * base_returns["strategy_medium_aggressive"]
                + weights[2] * base_returns["strategy_aggressive"]
            )
            mix_returns[name] = ret
            rows.append(metric_row(name, ret, weights))

    mix_returns_df = pd.DataFrame(mix_returns, index=returns.index)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(REPORTS / "strategy_mix_metrics.csv", index=False, float_format="%.8f")
    mix_returns_df.to_csv(REPORTS / "strategy_mix_returns.csv", index_label="date", float_format="%.8f")
    write_html(metrics)
    print((REPORTS / "strategy_mix_report.html").resolve())
    print(metrics.sort_values(["return_to_dd", "cagr"], ascending=[False, False]).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
