from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
PORTFOLIOS = [
    "strategy",
    "strategy_recommended_mix",
    "strategy_medium_aggressive",
    "strategy_aggressive",
    "benchmark_100_equity",
    "benchmark_80_20",
    "benchmark_60_40",
]
LABELS = {
    "strategy": "Strategia",
    "strategy_recommended_mix": "Rekomendowany miks",
    "strategy_medium_aggressive": "Srednio agresywna",
    "strategy_aggressive": "Agresywna",
    "benchmark_100_equity": "100% akcje",
    "benchmark_80_20": "80/20",
    "benchmark_60_40": "60/40",
}
METRICS = ["total_return", "cagr", "max_drawdown", "volatility", "sharpe_0rf"]


def pct(value: float) -> str:
    return f"{value:.1%}"


def metric_label(metric: str) -> str:
    return {
        "total_return": "Zwrot laczny",
        "cagr": "CAGR",
        "max_drawdown": "Max DD",
        "volatility": "Zmiennosc",
        "sharpe_0rf": "Sharpe 0rf",
    }[metric]


def fmt_metric(metric: str, value: float) -> str:
    if metric == "sharpe_0rf":
        return f"{value:.2f}"
    return pct(value)


def blend(start: tuple[int, int, int], end: tuple[int, int, int], t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    r = int(start[0] + (end[0] - start[0]) * t)
    g = int(start[1] + (end[1] - start[1]) * t)
    b = int(start[2] + (end[2] - start[2]) * t)
    return f"rgb({r},{g},{b})"


def heat_color(row: pd.Series, value: float, metric: str) -> str:
    clean = row.dropna().astype(float)
    if clean.empty or clean.max() == clean.min():
        return "#f7f5ef"

    higher_is_better = metric not in {"volatility"}
    score = (value - clean.min()) / (clean.max() - clean.min())
    if not higher_is_better:
        score = 1.0 - score

    if score >= 0.5:
        return blend((247, 245, 239), (79, 151, 112), (score - 0.5) * 2.0)
    return blend((198, 77, 82), (247, 245, 239), score * 2.0)


def decade_name(year: int) -> str:
    start = year - (year % 10)
    return f"{start}-{start + 9}"


def portfolio_metrics(ret: pd.Series) -> dict[str, float]:
    ret = ret.dropna()
    wealth = (1.0 + ret).cumprod()
    years = len(ret) / 52.1775
    total_return = wealth.iloc[-1] - 1.0
    cagr = wealth.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else float("nan")
    volatility = ret.std() * math.sqrt(52.1775)
    drawdown = wealth / wealth.cummax() - 1.0
    sharpe = cagr / volatility if volatility > 0 else float("nan")
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": drawdown.min(),
        "volatility": volatility,
        "sharpe_0rf": sharpe,
    }


def build_decade_metrics(returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    decades = returns.index.year.map(decade_name)
    for decade, group in returns[PORTFOLIOS].groupby(decades):
        for portfolio in PORTFOLIOS:
            metrics = portfolio_metrics(group[portfolio])
            rows.append(
                {
                    "decade": decade,
                    "portfolio": portfolio,
                    "label": LABELS[portfolio],
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def metric_table(data: pd.DataFrame, metric: str) -> str:
    pivot = data.pivot(index="decade", columns="label", values=metric)
    ordered_cols = [LABELS[col] for col in PORTFOLIOS]
    pivot = pivot[ordered_cols]
    label_to_key = {label: key for key, label in LABELS.items()}
    header = "<tr><th>Dekada</th>" + "".join(
        f'<th data-portfolio="{label_to_key[col]}">{col}</th>' for col in pivot.columns
    ) + "</tr>"
    rows = []
    for decade, row in pivot.iterrows():
        cells = [f"<td class=\"year\">{decade}</td>"]
        best = row.max() if metric != "volatility" else row.min()
        for col in pivot.columns:
            key = label_to_key[col]
            value = float(row[col])
            cls = " best" if value == best else ""
            color = heat_color(row, value, metric)
            cells.append(
                f'<td class="{cls.strip()}" data-portfolio="{key}" style="background:{color}">{fmt_metric(metric, value)}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"""
    <section>
      <h2>{metric_label(metric)}</h2>
      <table>
        <thead>{header}</thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
"""


def write_html(data: pd.DataFrame) -> None:
    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Porownanie dekadowe</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    p {{ margin: 0 0 18px; color: #555; line-height: 1.45; }}
    .selector {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 20px; background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .selector label {{ font-size: 13px; font-weight: 700; color: #444; }}
    .selector select {{ min-width: 280px; padding: 8px 10px; border: 1px solid #bdb6a7; background: #fff; font: inherit; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; border-right: 1px solid #eee8dc; text-align: right; font-size: 13px; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; }}
    td.year {{ background: #fff !important; font-weight: 600; }}
    td.best {{ font-weight: 800; box-shadow: inset 0 0 0 2px rgba(34, 83, 63, 0.28); }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Porownanie dekadowe strategii i benchmarkow</h1>
    <p>Metryki liczone oddzielnie dla kazdej dekady kalendarzowej dla wybranej strategii oraz benchmarkow. Kolor jest liczony w ramach kazdej dekady: zielony oznacza lepszy wynik, czerwony gorszy. Dla Max DD najlepsza jest najmniej ujemna wartosc, a dla zmiennosci najnizsza wartosc. <a href="decade_metrics.csv">CSV</a></p>
    <div class="selector">
      <label for="strategy-select">Strategia raportu</label>
      <select id="strategy-select">
        <option value="strategy_recommended_mix">Rekomendowany miks 30/70/0</option>
        <option value="strategy">Strategia bazowa</option>
        <option value="strategy_medium_aggressive">Strategia srednio agresywna</option>
        <option value="strategy_aggressive">Strategia agresywna</option>
      </select>
    </div>
    {''.join(metric_table(data, metric) for metric in METRICS)}
  </main>
  <script>
    (function () {{
      const storageKey = "invStrManualPortfolio.v4";
      const strategyKeys = new Set(["strategy", "strategy_recommended_mix", "strategy_medium_aggressive", "strategy_aggressive"]);
      const select = document.getElementById("strategy-select");
      function savedStrategy() {{
        try {{
          const saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
          return strategyKeys.has(saved.strategy) ? saved.strategy : "strategy_recommended_mix";
        }} catch (error) {{
          return "strategy_recommended_mix";
        }}
      }}
      function applyStrategy(strategy) {{
        select.value = strategyKeys.has(strategy) ? strategy : "strategy_recommended_mix";
        document.querySelectorAll("[data-portfolio]").forEach((cell) => {{
          const key = cell.dataset.portfolio;
          cell.hidden = strategyKeys.has(key) && key !== select.value;
        }});
        let saved = {{}};
        try {{ saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}"); }} catch (error) {{ saved = {{}}; }}
        saved.strategy = select.value;
        localStorage.setItem(storageKey, JSON.stringify(saved));
      }}
      select.addEventListener("change", () => applyStrategy(select.value));
      applyStrategy(savedStrategy());
    }})();
  </script>
  <script src="../assets/back_to_top.js"></script>
</body>
</html>
"""
    (REPORTS / "decade_comparison.html").write_text(html, encoding="utf-8")


def main() -> None:
    returns = pd.read_csv(REPORTS / "returns.csv", parse_dates=["date"]).set_index("date")
    data = build_decade_metrics(returns)
    data.to_csv(REPORTS / "decade_metrics.csv", index=False, float_format="%.8f")
    write_html(data)
    print((REPORTS / "decade_comparison.html").resolve())
    print(data.pivot(index="decade", columns="label", values="cagr").to_string(float_format=lambda value: f"{value:.2%}"))


if __name__ == "__main__":
    main()
