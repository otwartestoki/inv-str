from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def fmt_pct(value: float) -> str:
    return f"{value:.1%}"


def main() -> None:
    allocations = pd.read_csv(REPORTS / "allocations.csv", parse_dates=["date"]).set_index("date")
    weekly = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    asset_cols = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
    allocations[asset_cols] = allocations[asset_cols].astype(float)

    yearly = pd.DataFrame(index=allocations.resample("YE").mean().index.year)
    strategy_equity = allocations[["us_equity", "world_equity", "tech_equity"]].sum(axis=1)
    strategy_bonds_cash = allocations[["fixed_bond", "long_bond", "floating_bond"]].sum(axis=1)
    strategy_long_bonds = allocations["long_bond"]
    strategy_gold = allocations["gold"]
    medium_aggressive_equity = weekly[["med_aggr_w_us_equity", "med_aggr_w_world_equity", "med_aggr_w_tech_equity"]].sum(axis=1)
    aggressive_equity = weekly[["aggr_w_us_equity", "aggr_w_world_equity", "aggr_w_tech_equity"]].sum(axis=1)
    recommended_mix_equity = 0.30 * strategy_equity + 0.70 * medium_aggressive_equity

    grouped = pd.DataFrame(
        {
            "strategy_equity": strategy_equity,
            "strategy_bonds_cash": strategy_bonds_cash,
            "strategy_long_bonds": strategy_long_bonds,
            "strategy_gold": strategy_gold,
            "recommended_mix_equity_exposure": recommended_mix_equity,
            "medium_aggressive_equity_exposure": medium_aggressive_equity,
            "aggressive_equity_exposure": aggressive_equity,
        },
        index=allocations.index,
    ).resample("YE").mean()

    yearly["strategy_equity"] = grouped["strategy_equity"].values
    yearly["strategy_bonds_cash"] = grouped["strategy_bonds_cash"].values
    yearly["strategy_long_bonds"] = grouped["strategy_long_bonds"].values
    yearly["strategy_gold"] = grouped["strategy_gold"].values
    yearly["recommended_mix_equity_exposure"] = grouped["recommended_mix_equity_exposure"].values
    yearly["medium_aggressive_equity_exposure"] = grouped["medium_aggressive_equity_exposure"].values
    yearly["aggressive_equity_exposure"] = grouped["aggressive_equity_exposure"].values
    yearly["benchmark_60_40_equity"] = 0.60
    yearly["benchmark_60_40_bonds"] = 0.40
    yearly["benchmark_80_20_equity"] = 0.80
    yearly["benchmark_80_20_bonds"] = 0.20
    yearly["benchmark_100_equity"] = 1.00
    yearly["benchmark_100_bonds"] = 0.00

    yearly.index.name = "year"
    yearly.to_csv(REPORTS / "yearly_allocation_mix.csv", float_format="%.6f")

    display = yearly.copy()
    for col in display.columns:
        display[col] = display[col].map(fmt_pct)

    rows = []
    for year, row in display.iterrows():
        rows.append(
            "<tr>"
            f"<td>{year}</td>"
            f"<td data-portfolio=\"strategy\">{row['strategy_equity']}</td>"
            f"<td data-portfolio=\"strategy\">{row['strategy_bonds_cash']}</td>"
            f"<td data-portfolio=\"strategy\">{row['strategy_long_bonds']}</td>"
            f"<td data-portfolio=\"strategy\">{row['strategy_gold']}</td>"
            f"<td data-portfolio=\"strategy_recommended_mix\">{row['recommended_mix_equity_exposure']}</td>"
            f"<td data-portfolio=\"strategy_medium_aggressive\">{row['medium_aggressive_equity_exposure']}</td>"
            f"<td data-portfolio=\"strategy_aggressive\">{row['aggressive_equity_exposure']}</td>"
            f"<td>{row['benchmark_60_40_equity']}</td>"
            f"<td>{row['benchmark_60_40_bonds']}</td>"
            f"<td>{row['benchmark_80_20_equity']}</td>"
            f"<td>{row['benchmark_80_20_bonds']}</td>"
            f"<td>{row['benchmark_100_equity']}</td>"
            f"<td>{row['benchmark_100_bonds']}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Roczna alokacja</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    p {{ margin: 0 0 18px; color: #555; }}
    .selector {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 20px; background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .selector label {{ font-size: 13px; font-weight: 700; color: #444; }}
    .selector select {{ min-width: 280px; padding: 8px 10px; border: 1px solid #bdb6a7; background: #fff; font: inherit; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; text-align: right; font-size: 13px; }}
    th:first-child, td:first-child {{ text-align: left; position: sticky; left: 0; background: #fff; }}
    th {{ background: #f1eee6; font-weight: 700; }}
    tr:hover td {{ background: #f7f5ef; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Roczne proporcje akcje / obligacje</h1>
    <p>Srednia roczna alokacja wybranej strategii oraz stale benchmarki. W miksach agresywnych ekspozycja moze przekraczac 100%. <a href="yearly_allocation_mix.csv">CSV</a></p>
    <div class="selector">
      <label for="strategy-select">Strategia raportu</label>
      <select id="strategy-select">
        <option value="strategy_recommended_mix">Rekomendowany miks 30/70/0</option>
        <option value="strategy">Strategia bazowa</option>
        <option value="strategy_medium_aggressive">Strategia srednio agresywna</option>
        <option value="strategy_aggressive">Strategia agresywna</option>
      </select>
    </div>
    <table>
      <thead>
        <tr>
          <th>Rok</th>
          <th data-portfolio="strategy">Strategia akcje</th>
          <th data-portfolio="strategy">Strategia obligacje/gotowka</th>
          <th data-portfolio="strategy">Strategia obligacje 30+</th>
          <th data-portfolio="strategy">Strategia zloto</th>
          <th data-portfolio="strategy_recommended_mix">Rekomendowany miks eksp. akcji</th>
          <th data-portfolio="strategy_medium_aggressive">Srednio agresywna eksp. akcji</th>
          <th data-portfolio="strategy_aggressive">Agresywna eksp. akcji</th>
          <th>60/40 akcje</th>
          <th>60/40 obligacje</th>
          <th>80/20 akcje</th>
          <th>80/20 obligacje</th>
          <th>100% akcje</th>
          <th>100% obligacje</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
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
    (REPORTS / "yearly_allocation_mix.html").write_text(html, encoding="utf-8")
    print((REPORTS / "yearly_allocation_mix.html").resolve())
    print(yearly.tail(12).to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
