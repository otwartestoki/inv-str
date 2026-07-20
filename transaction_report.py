from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
ASSETS = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
BASE_WEIGHT = 0.30
MEDIUM_WEIGHT = 0.70
STRATEGIES = {
    "strategy_recommended_mix": "Rekomendowany miks 30/70/0",
    "strategy": "Strategia bazowa",
    "strategy_medium_aggressive": "Strategia srednio agresywna",
    "strategy_aggressive": "Strategia agresywna",
}
WEIGHT_PREFIXES = {
    "strategy": "w_",
    "strategy_medium_aggressive": "med_aggr_w_",
    "strategy_aggressive": "aggr_w_",
}
LABELS = {
    "us_equity": "SPX",
    "world_equity": "World",
    "tech_equity": "NDX",
    "fixed_bond": "Obligacje stale",
    "long_bond": "Obligacje 30+/TLT",
    "floating_bond": "Obligacje/gotowka",
    "gold": "Zloto",
}


def pct(value: float) -> str:
    return f"{value:.2%}"


def money(value: float) -> str:
    return f"${value:,.2f}"


def prefixed_weights(panel: pd.DataFrame, prefix: str) -> pd.DataFrame:
    weights = pd.DataFrame(index=panel.index)
    for asset in ASSETS:
        weights[asset] = panel[f"{prefix}{asset}"].astype(float)
    return weights


def recommended_mix_weights(panel: pd.DataFrame) -> pd.DataFrame:
    base_weights = prefixed_weights(panel, "w_")
    medium_weights = prefixed_weights(panel, "med_aggr_w_")
    return BASE_WEIGHT * base_weights + MEDIUM_WEIGHT * medium_weights


def strategy_weights(panel: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if strategy == "strategy_recommended_mix":
        return recommended_mix_weights(panel)
    return prefixed_weights(panel, WEIGHT_PREFIXES[strategy])


def build_transactions_for_strategy(panel: pd.DataFrame, strategy: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = strategy_weights(panel, strategy)
    deltas = weights.diff()
    deltas.iloc[0] = weights.iloc[0]
    turnover = deltas.abs().sum(axis=1)

    wealth = (1.0 + panel[strategy]).cumprod() * 100.0
    wealth_before = wealth.shift(1).fillna(100.0)

    rows = []
    details = []
    changed_dates = turnover[turnover > 1e-10].index

    previous_weights = pd.Series(0.0, index=ASSETS)
    for date in changed_dates:
        target = weights.loc[date, ASSETS]
        delta = target - previous_weights
        portfolio_value = float(wealth_before.loc[date])
        trade_notional = delta * portfolio_value

        buys = []
        sells = []
        for asset in ASSETS:
            notional = float(trade_notional[asset])
            if abs(notional) < 0.01:
                continue

            label = LABELS[asset]
            old_weight = float(previous_weights[asset])
            new_weight = float(target[asset])
            delta_weight = new_weight - old_weight
            details.append(
                {
                    "strategy": strategy,
                    "strategy_label": STRATEGIES[strategy],
                    "date": date,
                    "asset": asset,
                    "asset_label": label,
                    "old_weight": old_weight,
                    "new_weight": new_weight,
                    "delta_weight": delta_weight,
                    "portfolio_value_before": portfolio_value,
                    "trade_notional": notional,
                    "side": "BUY" if notional > 0 else "SELL",
                }
            )

            text = f"{label} {pct(abs(delta_weight))} ({money(abs(notional))})"
            if notional > 0:
                buys.append(text)
            else:
                sells.append(text)

        rows.append(
            {
                "strategy": strategy,
                "strategy_label": STRATEGIES[strategy],
                "date": date,
                "portfolio_value_before": portfolio_value,
                "turnover": float(turnover.loc[date]),
                "buy": ", ".join(buys),
                "sell": ", ".join(sells),
                "target_equity": float(target[["us_equity", "world_equity", "tech_equity"]].sum()),
                "target_bonds_cash": float(target[["fixed_bond", "long_bond", "floating_bond"]].sum()),
                "target_gold": float(target["gold"]),
            }
        )
        previous_weights = target.copy()

    return pd.DataFrame(rows), pd.DataFrame(details)


def build_transactions() -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    summaries = []
    details = []
    for strategy in STRATEGIES:
        summary, detail = build_transactions_for_strategy(panel, strategy)
        summaries.append(summary)
        details.append(detail)
    return pd.concat(summaries, ignore_index=True), pd.concat(details, ignore_index=True)


def table_for_strategy(summary: pd.DataFrame, strategy: str) -> str:
    rows = []
    for _, row in summary[summary["strategy"] == strategy].iterrows():
        rows.append(
            "<tr>"
            f"<td>{row['date'].date()}</td>"
            f"<td>{money(row['portfolio_value_before'])}</td>"
            f"<td>{pct(row['turnover'])}</td>"
            f"<td>{row['buy']}</td>"
            f"<td>{row['sell']}</td>"
            f"<td>{pct(row['target_equity'])}</td>"
            f"<td>{pct(row['target_bonds_cash'])}</td>"
            f"<td>{pct(row['target_gold'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def stats_for_strategy(summary: pd.DataFrame, strategy: str) -> tuple[float, float, float, int]:
    strategy_summary = summary[summary["strategy"] == strategy]
    if strategy_summary.empty:
        return 0.0, 0.0, 0.0, 0
    return (
        float(strategy_summary["turnover"].sum()),
        float(strategy_summary["turnover"].mean()),
        float(strategy_summary["turnover"].max()),
        int(len(strategy_summary)),
    )


def write_html(summary: pd.DataFrame, detail: pd.DataFrame) -> None:
    options = "".join(f'<option value="{key}">{label}</option>' for key, label in STRATEGIES.items())
    sections = []
    for strategy, label in STRATEGIES.items():
        total_turnover, avg_turnover, max_turnover, count = stats_for_strategy(summary, strategy)
        hidden = "" if strategy == "strategy_recommended_mix" else " hidden"
        sections.append(
            f"""
    <section class="strategy-report{hidden}" data-strategy-report="{strategy}">
      <h2>{label}</h2>
      <div class="stats">
        <div class="stat">Liczba rebalancingow<b>{count}</b></div>
        <div class="stat">Suma obrotu wagowego<b>{pct(total_turnover)}</b></div>
        <div class="stat">Sredni obrot<b>{pct(avg_turnover)}</b></div>
        <div class="stat">Najwiekszy obrot<b>{pct(max_turnover)}</b></div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Portfel przed</th>
            <th>Obrot</th>
            <th>Kupno</th>
            <th>Sprzedaz</th>
            <th>Akcje po</th>
            <th>Obligacje/gotowka po</th>
            <th>Zloto po</th>
          </tr>
        </thead>
        <tbody>{table_for_strategy(summary, strategy)}</tbody>
      </table>
    </section>
"""
        )

    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Transakcje i rebalancing</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 24px 0 10px; font-size: 18px; }}
    p {{ margin: 0 0 18px; color: #555; }}
    .selector {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 20px; background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .selector label {{ font-size: 13px; font-weight: 700; color: #444; }}
    .selector select {{ min-width: 280px; padding: 8px 10px; border: 1px solid #bdb6a7; background: #fff; font: inherit; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 10px; margin: 18px 0 22px; }}
    .stat {{ background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .stat b {{ display: block; font-size: 20px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; text-align: right; font-size: 13px; vertical-align: top; }}
    th:first-child, td:first-child, th:nth-child(4), td:nth-child(4), th:nth-child(5), td:nth-child(5) {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; position: sticky; top: 0; }}
    tr:hover td {{ background: #f7f5ef; }}
    .strategy-report[hidden] {{ display: none; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Lista transakcji i rebalancing</h1>
    <p>Zmiany wag portfela po zastosowaniu progu rebalancingu 5 p.p.; kwoty sa orientacyjne dla portfela startowego 100 USD. Raport uzywa tej samej strategii, ktora jest wybrana na stronie glownej. <a href="transactions_summary.csv">CSV summary</a> / <a href="transactions_detail.csv">CSV detail</a></p>
    <div class="selector">
      <label for="strategy-select">Strategia raportu</label>
      <select id="strategy-select">{options}</select>
    </div>
    {''.join(sections)}
  </main>
  <script>
    (function () {{
      const storageKey = "invStrManualPortfolio.v4";
      const select = document.getElementById("strategy-select");
      const valid = new Set(Array.from(select.options).map((option) => option.value));
      function savedStrategy() {{
        try {{
          const saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
          return valid.has(saved.strategy) ? saved.strategy : "strategy_recommended_mix";
        }} catch (error) {{
          return "strategy_recommended_mix";
        }}
      }}
      function saveStrategy(strategy) {{
        let saved = {{}};
        try {{ saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}"); }} catch (error) {{ saved = {{}}; }}
        saved.strategy = strategy;
        localStorage.setItem(storageKey, JSON.stringify(saved));
      }}
      function applyStrategy(strategy) {{
        select.value = valid.has(strategy) ? strategy : "strategy_recommended_mix";
        document.querySelectorAll("[data-strategy-report]").forEach((section) => {{
          section.hidden = section.dataset.strategyReport !== select.value;
        }});
        saveStrategy(select.value);
      }}
      select.addEventListener("change", () => applyStrategy(select.value));
      applyStrategy(savedStrategy());
    }})();
  </script>
  <script src="../assets/back_to_top.js"></script>
</body>
</html>
"""
    (REPORTS / "transactions_rebalancing.html").write_text(html, encoding="utf-8")


def main() -> None:
    summary, detail = build_transactions()
    summary.to_csv(REPORTS / "transactions_summary.csv", index=False, float_format="%.8f")
    detail.to_csv(REPORTS / "transactions_detail.csv", index=False, float_format="%.8f")
    write_html(summary, detail)
    print((REPORTS / "transactions_rebalancing.html").resolve())
    print(summary.tail(15).to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
