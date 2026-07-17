from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def polyline(index: pd.DatetimeIndex, values: pd.Series, x_func, y_func) -> str:
    return " ".join(f"{x_func(i):.2f},{y_func(float(v)):.2f}" for i, v in enumerate(values))


def contiguous_regions(mask: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    regions = []
    start = None
    prev = None
    for date, value in mask.items():
        if value and start is None:
            start = date
        if not value and start is not None:
            regions.append((start, prev))
            start = None
        prev = date
    if start is not None:
        regions.append((start, prev))
    return regions


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 720
    left, right, top, bottom = 82, 42, 62, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index

    fed = data["fed_funds"].astype(float)
    unemp = data["unemployment"].astype(float)
    s2 = data["s2_equity"].astype(float)
    cross = data["fed_unemployment_bear_cross"].fillna(False).astype(bool)
    spx = data["sp_price"].astype(float).replace(0.0, np.nan).ffill()
    spx_log = np.log(spx)
    spx_min = float(spx_log.min())
    spx_max = float(spx_log.max())

    y_max = max(12.0, float(np.nanmax([fed.max(), unemp.max()])))
    y_max = np.ceil(y_max)

    def x_pos(i: int) -> float:
        return left + i / max(len(dates) - 1, 1) * plot_w

    def x_date(date: pd.Timestamp) -> float:
        return x_pos(dates.get_loc(date))

    def y_pos(value: float) -> float:
        return top + plot_h - value / y_max * plot_h

    def y_spx(value: float) -> float:
        if spx_max == spx_min:
            return top + plot_h / 2
        scaled = (np.log(value) - spx_min) / (spx_max - spx_min)
        return top + plot_h - scaled * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Fed Funds vs bezrobocie USA na tle S&amp;P 500</text>',
        f'<text class="small" x="{left}" y="56">Szare tlo liniowe: SPX w skali log, znormalizowany; czerwone tlo: modul cyklu defensywny 0% akcji</text>',
    ]

    defensive = s2 <= 0.20
    for start, end in contiguous_regions(defensive):
        x1 = x_date(start)
        x2 = x_date(end)
        lines.append(f'<rect x="{x1:.2f}" y="{top}" width="{max(x2 - x1, 1):.2f}" height="{plot_h}" fill="#f2b8a8" opacity="0.22"/>')

    for value in np.arange(0.0, y_max + 0.1, 1.0):
        y = y_pos(float(value))
        stroke = "#d8d8d1" if value % 2 == 0 else "#eeeeea"
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="{stroke}" stroke-width="1"/>')
        if value % 2 == 0:
            lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{value:.0f}%</text>')

    year_ticks = pd.date_range(dates.min(), dates.max(), freq="5YS")
    for tick in year_ticks:
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_pos(idx)
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 44}" text-anchor="middle">{tick.year}</text>')

    for date in cross[cross].index:
        x = x_date(date)
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#7f1d1d" stroke-width="1.4" opacity="0.55"/>')

    lines.append(
        f'<polyline fill="none" stroke="#8f8f88" stroke-width="2.2" opacity="0.42" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{polyline(dates, spx, x_pos, y_spx)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#c1121f" stroke-width="3" stroke-linejoin="round" '
        f'stroke-linecap="round" points="{polyline(dates, fed, x_pos, y_pos)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#15616d" stroke-width="3" stroke-linejoin="round" '
        f'stroke-linecap="round" points="{polyline(dates, unemp, x_pos, y_pos)}"/>'
    )

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Poziom, %</text>')

    legend_x, legend_y = left + 18, top + 24
    items = [
        ("#c1121f", "Fed Funds"),
        ("#15616d", "Bezrobocie"),
        ("#7f1d1d", "Przeciecie od gory"),
        ("#8f8f88", "S&amp;P 500, log"),
    ]
    for i, (color, label) in enumerate(items):
        y = legend_y + i * 25
        lines.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="4" opacity="0.85"/>')
        lines.append(f'<text class="small" x="{legend_x + 44}" y="{y + 5}">{label}</text>')

    last = data.iloc[-1]
    lines.append(
        f'<text class="small" x="{left + plot_w - 260}" y="{top + 24}">Ostatnio: Fed {last.fed_funds:.2f}%, '
        f'bezrobocie {last.unemployment:.2f}%, cykl {last.s2_equity:.0%} akcji</text>'
    )

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "rates_vs_unemployment.svg")
    crosses = data.loc[data["fed_unemployment_bear_cross"].fillna(False), ["fed_funds", "unemployment", "s2_equity"]]
    crosses.to_csv(REPORTS / "rates_unemployment_crosses.csv", index_label="date")
    print((REPORTS / "rates_vs_unemployment.svg").resolve())
    print(crosses.tail(20).to_string())


if __name__ == "__main__":
    main()
