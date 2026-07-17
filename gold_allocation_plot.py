from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def polyline(values: pd.Series, x_func, y_func) -> str:
    return " ".join(f"{x_func(i):.2f},{y_func(float(v)):.2f}" for i, v in enumerate(values))


def regions(mask: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out = []
    start = None
    prev = None
    for date, value in mask.items():
        if value and start is None:
            start = date
        if not value and start is not None:
            out.append((start, prev))
            start = None
        prev = date
    if start is not None:
        out.append((start, prev))
    return out


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1180, 540
    left, right, top, bottom = 82, 40, 62, 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index
    gold = data["w_gold"].clip(0.0, 0.20)
    gold_mode = data["gold_mode"].astype(bool)
    gold_index = (1.0 + data["gold_ret"].astype(float).fillna(0.0)).cumprod() * 100.0
    gold_log = np.log(gold_index.replace(0.0, np.nan).ffill())
    gold_log_min = float(gold_log.min())
    gold_log_max = float(gold_log.max())

    def x_pos(i: int) -> float:
        return left + i / max(len(dates) - 1, 1) * plot_w

    def x_date(date: pd.Timestamp) -> float:
        return x_pos(dates.get_loc(date))

    def y_pos(value: float) -> float:
        return top + plot_h - value / 0.20 * plot_h

    def y_gold_price(value: float) -> float:
        if gold_log_max == gold_log_min:
            return top + plot_h / 2
        scaled = (np.log(value) - gold_log_min) / (gold_log_max - gold_log_min)
        return top + plot_h - scaled * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Udzial zlota w portfelu na tle ceny zlota</text>',
        f'<text class="small" x="{left}" y="56">Szara linia: indeks zlota od 100, skala log; zlota linia: udzial zlota w portfelu</text>',
    ]

    for start, end in regions(gold_mode):
        x1 = x_date(start)
        x2 = x_date(end)
        lines.append(f'<rect x="{x1:.2f}" y="{top}" width="{max(x2 - x1, 1):.2f}" height="{plot_h}" fill="#f2c14e" opacity="0.22"/>')

    for pct in np.arange(0.0, 0.201, 0.025):
        y = y_pos(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        if abs((pct * 100) % 5) < 0.001:
            lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')

    year_ticks = pd.date_range(dates.min(), dates.max(), freq="5YS")
    for tick in year_ticks:
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_pos(idx)
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 40}" text-anchor="middle">{tick.year}</text>')

    lines.append(
        f'<polyline fill="none" stroke="#8f8f88" stroke-width="2.2" opacity="0.45" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{polyline(gold_index, x_pos, y_gold_price)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#b8860b" stroke-width="3" stroke-linejoin="round" '
        f'stroke-linecap="round" points="{polyline(gold, x_pos, y_pos)}"/>'
    )
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Zloto w portfelu</text>')

    active = gold[gold > 0]
    label = "brak aktywnej pozycji" if active.empty else f"aktywnie {len(active)} tyg.; max {active.max():.0%}"
    lines.append(f'<line x1="{left + 18}" y1="{top + 24}" x2="{left + 52}" y2="{top + 24}" stroke="#b8860b" stroke-width="4"/>')
    lines.append(f'<text class="small" x="{left + 62}" y="{top + 29}">Zloto: {label}; teraz {gold.iloc[-1]:.0%}</text>')
    lines.append(f'<line x1="{left + 18}" y1="{top + 49}" x2="{left + 52}" y2="{top + 49}" stroke="#8f8f88" stroke-width="4" opacity="0.55"/>')
    lines.append(f'<text class="small" x="{left + 62}" y="{top + 54}">Indeks ceny zlota: {gold_index.iloc[-1]:,.0f}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "gold_allocation.svg")
    out = data.loc[data["w_gold"] > 0, ["w_gold", "gold_mode", "fed_funds"]]
    out.to_csv(REPORTS / "gold_allocation_periods.csv", index_label="date")
    print((REPORTS / "gold_allocation.svg").resolve())
    if out.empty:
        print("No gold allocation")
    else:
        print(out.resample("YE").max().loc[lambda x: x["w_gold"] > 0].to_string())


if __name__ == "__main__":
    main()
