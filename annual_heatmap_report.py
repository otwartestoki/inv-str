from __future__ import annotations

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


def pct(value: float) -> str:
    return f"{value:.1%}"


def return_color(value: float) -> str:
    value = max(-0.40, min(0.40, float(value)))
    if value >= 0:
        intensity = value / 0.40
        r = int(244 - 120 * intensity)
        g = int(247 - 75 * intensity)
        b = int(241 - 125 * intensity)
    else:
        intensity = abs(value) / 0.40
        r = int(250 - 45 * intensity)
        g = int(243 - 135 * intensity)
        b = int(235 - 145 * intensity)
    return f"rgb({r},{g},{b})"


def dd_color(value: float) -> str:
    value = abs(max(-0.60, min(0.0, float(value))))
    intensity = value / 0.60
    r = int(247 - 90 * intensity)
    g = int(246 - 150 * intensity)
    b = int(242 - 160 * intensity)
    return f"rgb({r},{g},{b})"


def annual_metrics(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual_return = returns[PORTFOLIOS].resample("YE").apply(lambda x: (1.0 + x).prod() - 1.0)
    annual_return.index = annual_return.index.year

    rows = []
    for year, group in returns[PORTFOLIOS].groupby(returns.index.year):
        wealth = (1.0 + group).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        rows.append(drawdown.min().rename(year))
    annual_dd = pd.DataFrame(rows)
    annual_dd.index.name = "year"
    annual_return.index.name = "year"
    return annual_return, annual_dd


def heatmap_table(df: pd.DataFrame, title: str, color_func) -> str:
    header = "<tr><th>Rok</th>" + "".join(
        f'<th data-portfolio="{col}">{LABELS[col]}</th>' for col in df.columns
    ) + "</tr>"
    rows = []
    for year, row in df.iterrows():
        cells = [f"<td class=\"year\">{year}</td>"]
        for col in df.columns:
            value = float(row[col])
            cells.append(f'<td data-portfolio="{col}" style="background:{color_func(value)}">{pct(value)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"""
    <section>
      <h2>{title}</h2>
      <table>
        <thead>{header}</thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
"""


def write_html(annual_return: pd.DataFrame, annual_dd: pd.DataFrame) -> None:
    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Heatmapa rocznych wynikow</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    p {{ margin: 0 0 18px; color: #555; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    .selector {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 20px; background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .selector label {{ font-size: 13px; font-weight: 700; color: #444; }}
    .selector select {{ min-width: 280px; padding: 8px 10px; border: 1px solid #bdb6a7; background: #fff; font: inherit; }}
    th, td {{ padding: 7px 9px; border-bottom: 1px solid #e6e1d6; border-right: 1px solid #eee8dc; text-align: right; font-size: 13px; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; }}
    td.year {{ background: #fff; font-weight: 600; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Heatmapa rocznych wynikow i drawdown</h1>
    <p>Roczne stopy zwrotu i maksymalne obsuniecia w danym roku dla wybranej strategii oraz benchmarkow. <a href="annual_return_heatmap.csv">CSV zwrotow</a> / <a href="annual_drawdown_heatmap.csv">CSV drawdown</a></p>
    <div class="selector">
      <label for="strategy-select">Strategia raportu</label>
      <select id="strategy-select">
        <option value="strategy_recommended_mix">Rekomendowany miks 30/70/0</option>
        <option value="strategy">Strategia bazowa</option>
        <option value="strategy_medium_aggressive">Strategia srednio agresywna</option>
        <option value="strategy_aggressive">Strategia agresywna</option>
      </select>
    </div>
    {heatmap_table(annual_return, "Roczny zysk / strata", return_color)}
    {heatmap_table(annual_dd, "Maksymalny drawdown w roku", dd_color)}
  </main>
  <script>
    (function () {{
      const storageKey = "invStrManualPortfolio.v4";
      const strategyKeys = new Set(["strategy", "strategy_recommended_mix", "strategy_medium_aggressive", "strategy_aggressive"]);
      const benchmarkKeys = new Set(["benchmark_100_equity", "benchmark_80_20", "benchmark_60_40"]);
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
</body>
</html>
"""
    (REPORTS / "annual_heatmap.html").write_text(html, encoding="utf-8")


def main() -> None:
    returns = pd.read_csv(REPORTS / "returns.csv", parse_dates=["date"]).set_index("date")
    annual_return, annual_dd = annual_metrics(returns)
    annual_return.to_csv(REPORTS / "annual_return_heatmap.csv", float_format="%.8f")
    annual_dd.to_csv(REPORTS / "annual_drawdown_heatmap.csv", float_format="%.8f")
    write_html(annual_return, annual_dd)
    print((REPORTS / "annual_heatmap.html").resolve())
    print(annual_return.tail(10).to_string(float_format=lambda value: f"{value:.2%}"))


if __name__ == "__main__":
    main()
