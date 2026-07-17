from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.2%}"


def num(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.2f}"


def bond_mode(row: pd.Series) -> str:
    if row["long_bond"] > row["floating_bond"]:
        return "30+"
    if row["floating_bond"] > row["fixed_bond"]:
        return "zmienne"
    return "mieszane"


def build_switches() -> pd.DataFrame:
    allocations = pd.read_csv(REPORTS / "allocations.csv", parse_dates=["date"]).set_index("date")
    panel = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")

    data = allocations.join(
        panel[["fed_funds", "dgs10", "cpi_yoy", "real_10y", "gdp_yoy", "fixed_bond_mode", "long_bond_share"]],
        how="left",
    )
    data["bond_mode"] = data.apply(bond_mode, axis=1)
    data["previous_bond_mode"] = data["bond_mode"].shift(1)

    switches = data[
        data["previous_bond_mode"].notna()
        & (data["bond_mode"] != data["previous_bond_mode"])
        & data["bond_mode"].isin(["30+", "zmienne"])
        & data["previous_bond_mode"].isin(["30+", "zmienne"])
    ].copy()

    switches["direction"] = switches["previous_bond_mode"] + " -> " + switches["bond_mode"]
    switches["bond_weight"] = switches["fixed_bond"] + switches["long_bond"] + switches["floating_bond"]
    switches = switches.reset_index()
    return switches[
        [
            "date",
            "direction",
            "fixed_bond",
            "long_bond",
            "floating_bond",
            "bond_weight",
            "target_equity",
            "gold",
            "fed_funds",
            "dgs10",
            "cpi_yoy",
            "real_10y",
            "gdp_yoy",
            "fixed_bond_mode",
            "long_bond_share",
        ]
    ]


def write_html(switches: pd.DataFrame) -> None:
    to_fixed = int((switches["direction"] == "zmienne -> 30+").sum()) if not switches.empty else 0
    to_floating = int((switches["direction"] == "30+ -> zmienne").sum()) if not switches.empty else 0
    last = switches.iloc[-1] if not switches.empty else None

    rows = []
    for _, row in switches.iterrows():
        rows.append(
            "<tr>"
            f"<td>{row['date'].date()}</td>"
            f"<td>{row['direction']}</td>"
            f"<td>{pct(row['long_bond'])}</td>"
            f"<td>{pct(row['floating_bond'])}</td>"
            f"<td>{pct(row['long_bond_share'])}</td>"
            f"<td>{pct(row['bond_weight'])}</td>"
            f"<td>{pct(row['target_equity'])}</td>"
            f"<td>{pct(row['gold'])}</td>"
            f"<td>{num(row['fed_funds'])}%</td>"
            f"<td>{num(row['dgs10'])}%</td>"
            f"<td>{num(row['cpi_yoy'])}%</td>"
            f"<td>{num(row['real_10y'])}%</td>"
            f"<td>{num(row['gdp_yoy'])}%</td>"
            "</tr>"
        )

    last_text = "brak" if last is None else f"{last['date'].date()} ({last['direction']})"
    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Przejscia obligacji</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #fbfbf8; color: #222; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    p {{ margin: 0 0 18px; color: #555; }}
    .stats {{ display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 10px; margin: 18px 0 22px; }}
    .stat {{ background: #fff; border: 1px solid #ddd8cc; padding: 12px; }}
    .stat b {{ display: block; font-size: 20px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd8cc; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6e1d6; text-align: right; font-size: 13px; vertical-align: top; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ background: #f1eee6; font-weight: 700; position: sticky; top: 0; }}
    tr:hover td {{ background: #f7f5ef; }}
    a {{ color: #15616d; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Przejscia obligacji 30+ / zmiennoprocentowe</h1>
    <p>Daty, w ktorych defensywna czesc portfela zmieniala dominujacy typ obligacji: duration 30+ albo zmiennoprocentowe/gotowka. <a href="bond_switches.csv">CSV</a></p>
    <div class="stats">
      <div class="stat">Przejscia na 30+<b>{to_fixed}</b></div>
      <div class="stat">Przejscia na zmienne<b>{to_floating}</b></div>
      <div class="stat">Ostatnie przejscie<b>{last_text}</b></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Zmiana</th>
          <th>Obligacje 30+</th>
          <th>Zmiennoprocentowe/gotowka</th>
          <th>Udzial 30+ w czesci obligacyjnej</th>
          <th>Czesc obligacyjna</th>
          <th>Akcje</th>
          <th>Zloto</th>
          <th>Fed Funds</th>
          <th>10Y</th>
          <th>CPI YoY</th>
          <th>Real 10Y</th>
          <th>GDP YoY</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""
    (REPORTS / "bond_switches.html").write_text(html, encoding="utf-8")


def main() -> None:
    switches = build_switches()
    switches.to_csv(REPORTS / "bond_switches.csv", index=False, float_format="%.8f")
    write_html(switches)
    print((REPORTS / "bond_switches.html").resolve())
    print(switches.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
