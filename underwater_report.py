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


def weeks_to_text(weeks: int) -> str:
    years = weeks / 52.1775
    if weeks < 52:
        return f"{weeks} tyg."
    return f"{weeks} tyg. ({years:.1f} lat)"


def pct(value: float) -> str:
    return f"{value:.1%}"


def underwater_periods(ret: pd.Series) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    wealth = (1.0 + ret.dropna()).cumprod()
    high = wealth.cummax()
    drawdown = wealth / high - 1.0
    underwater = drawdown < -1e-12

    durations = []
    current = 0
    for is_underwater in underwater:
        current = current + 1 if bool(is_underwater) else 0
        durations.append(current)
    duration_series = pd.Series(durations, index=wealth.index, name="underwater_weeks")

    rows = []
    start = None
    trough_date = None
    trough_dd = 0.0
    for date, is_underwater in underwater.items():
        dd = float(drawdown.loc[date])
        if bool(is_underwater) and start is None:
            start = date
            trough_date = date
            trough_dd = dd
        elif bool(is_underwater):
            if dd < trough_dd:
                trough_dd = dd
                trough_date = date
        elif start is not None:
            end = date
            weeks = int(duration_series.shift(1).loc[date])
            rows.append(
                {
                    "start": start,
                    "recovered": end,
                    "weeks": weeks,
                    "years": weeks / 52.1775,
                    "trough_date": trough_date,
                    "max_drawdown": trough_dd,
                    "recovered_flag": True,
                }
            )
            start = None
            trough_date = None
            trough_dd = 0.0

    if start is not None:
        weeks = int(duration_series.iloc[-1])
        rows.append(
            {
                "start": start,
                "recovered": pd.NaT,
                "weeks": weeks,
                "years": weeks / 52.1775,
                "trough_date": trough_date,
                "max_drawdown": trough_dd,
                "recovered_flag": False,
            }
        )

    return pd.DataFrame(rows), duration_series, drawdown


def build_reports(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    all_periods = []
    duration_cols = []

    for portfolio in PORTFOLIOS:
        periods, duration, drawdown = underwater_periods(returns[portfolio])
        periods.insert(0, "portfolio", portfolio)
        periods.insert(1, "label", LABELS[portfolio])
        all_periods.append(periods)
        duration_cols.append(duration.rename(portfolio))

        completed = periods[periods["recovered_flag"]] if not periods.empty else periods
        longest = periods.sort_values("weeks", ascending=False).head(1)
        longest_row = longest.iloc[0] if not longest.empty else None
        summary_rows.append(
            {
                "portfolio": portfolio,
                "label": LABELS[portfolio],
                "time_underwater_pct": float((drawdown < -1e-12).mean()),
                "period_count": int(len(periods)),
                "completed_period_count": int(len(completed)),
                "avg_completed_weeks": float(completed["weeks"].mean()) if not completed.empty else 0.0,
                "median_completed_weeks": float(completed["weeks"].median()) if not completed.empty else 0.0,
                "longest_weeks": int(longest_row["weeks"]) if longest_row is not None else 0,
                "longest_years": float(longest_row["years"]) if longest_row is not None else 0.0,
                "longest_start": longest_row["start"] if longest_row is not None else pd.NaT,
                "longest_recovered": longest_row["recovered"] if longest_row is not None else pd.NaT,
                "longest_max_drawdown": float(longest_row["max_drawdown"]) if longest_row is not None else 0.0,
                "current_underwater_weeks": int(duration.iloc[-1]),
                "current_drawdown": float(drawdown.iloc[-1]),
            }
        )

    summary = pd.DataFrame(summary_rows)
    periods = pd.concat(all_periods, ignore_index=True) if all_periods else pd.DataFrame()
    duration_panel = pd.concat(duration_cols, axis=1)
    duration_panel.columns = [LABELS[col] for col in duration_panel.columns]
    return summary, periods, duration_panel


def write_html(summary: pd.DataFrame, periods: pd.DataFrame) -> None:
    summary_rows = []
    for _, row in summary.iterrows():
        recovered = row["longest_recovered"]
        recovered_text = "-" if pd.isna(recovered) else pd.Timestamp(recovered).date()
        summary_rows.append(
            f"<tr data-portfolio=\"{row['portfolio']}\">"
            f"<td>{row['label']}</td>"
            f"<td>{pct(row['time_underwater_pct'])}</td>"
            f"<td>{int(row['period_count'])}</td>"
            f"<td>{weeks_to_text(int(round(row['avg_completed_weeks'])))}</td>"
            f"<td>{weeks_to_text(int(row['longest_weeks']))}</td>"
            f"<td>{pd.Timestamp(row['longest_start']).date()}</td>"
            f"<td>{recovered_text}</td>"
            f"<td>{pct(row['longest_max_drawdown'])}</td>"
            f"<td>{weeks_to_text(int(row['current_underwater_weeks']))}</td>"
            f"<td>{pct(row['current_drawdown'])}</td>"
            "</tr>"
        )

    period_rows = []
    biggest = periods.sort_values(["portfolio", "weeks"], ascending=[True, False]).groupby("portfolio").head(10)
    for _, row in biggest.iterrows():
        recovered_text = "-" if pd.isna(row["recovered"]) else pd.Timestamp(row["recovered"]).date()
        period_rows.append(
            f"<tr data-portfolio=\"{row['portfolio']}\">"
            f"<td>{row['label']}</td>"
            f"<td>{pd.Timestamp(row['start']).date()}</td>"
            f"<td>{recovered_text}</td>"
            f"<td>{weeks_to_text(int(row['weeks']))}</td>"
            f"<td>{pd.Timestamp(row['trough_date']).date()}</td>"
            f"<td>{pct(row['max_drawdown'])}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Czas na stracie wzgledem ATH</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    p {{ margin: 0 0 18px; color: #555; line-height: 1.45; }}
    .selector {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 20px; background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .selector label {{ font-size: 13px; font-weight: 700; color: #444; }}
    .selector select {{ min-width: 280px; padding: 8px 10px; border: 1px solid #bdb6a7; background: #fff; font: inherit; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; border-right: 1px solid #eee8dc; text-align: right; font-size: 13px; vertical-align: top; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; }}
    tr:hover td {{ background: #f7f5ef; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Czas na stracie wzgledem poprzedniego szczytu</h1>
    <p>Analiza mierzy okresy, w ktorych kapital wybranej strategii oraz benchmarkow byl ponizej poprzedniego maksimum. Okres konczy sie dopiero po ustanowieniu nowego ATH. <a href="underwater_summary.csv">CSV summary</a> / <a href="underwater_periods.csv">CSV okresow</a> / <a href="underwater_duration_weeks.csv">CSV tygodniowy</a></p>
    <div class="selector">
      <label for="strategy-select">Strategia raportu</label>
      <select id="strategy-select">
        <option value="strategy_recommended_mix">Rekomendowany miks 30/70/0</option>
        <option value="strategy">Strategia bazowa</option>
        <option value="strategy_medium_aggressive">Strategia srednio agresywna</option>
        <option value="strategy_aggressive">Strategia agresywna</option>
      </select>
    </div>
    <h2>Podsumowanie</h2>
    <table>
      <thead>
        <tr>
          <th>Portfel</th>
          <th>Czas pod ATH</th>
          <th>Liczba okresow</th>
          <th>Sredni zakonczony okres</th>
          <th>Najdluzszy okres</th>
          <th>Start najdluzszego</th>
          <th>Odzyskanie ATH</th>
          <th>DD w najdluzszym</th>
          <th>Obecny okres</th>
          <th>Obecny DD</th>
        </tr>
      </thead>
      <tbody>{''.join(summary_rows)}</tbody>
    </table>
    <h2>Najdluzsze okresy na stracie</h2>
    <table>
      <thead>
        <tr>
          <th>Portfel</th>
          <th>Start</th>
          <th>Odzyskanie ATH</th>
          <th>Czas</th>
          <th>Najglebszy punkt</th>
          <th>Max DD</th>
        </tr>
      </thead>
      <tbody>{''.join(period_rows)}</tbody>
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
        document.querySelectorAll("[data-portfolio]").forEach((row) => {{
          const key = row.dataset.portfolio;
          row.hidden = strategyKeys.has(key) && key !== select.value;
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
    (REPORTS / "underwater_duration.html").write_text(html, encoding="utf-8")


def main() -> None:
    returns = pd.read_csv(REPORTS / "returns.csv", parse_dates=["date"]).set_index("date")
    summary, periods, duration_panel = build_reports(returns)
    summary.to_csv(REPORTS / "underwater_summary.csv", index=False, float_format="%.8f")
    periods.to_csv(REPORTS / "underwater_periods.csv", index=False, float_format="%.8f")
    duration_panel.to_csv(REPORTS / "underwater_duration_weeks.csv", index_label="date")
    write_html(summary, periods)
    print((REPORTS / "underwater_duration.html").resolve())
    print(summary[["label", "time_underwater_pct", "longest_weeks", "current_underwater_weeks", "current_drawdown"]].to_string(index=False))


if __name__ == "__main__":
    main()
