from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def points(dates: pd.DatetimeIndex, values: pd.Series, x_func, y_func) -> str:
    return " ".join(f"{x_func(i):.2f},{y_func(float(v)):.2f}" for i, v in enumerate(values))


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 640
    left, right, top, bottom = 86, 86, 62, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index

    strategy = data["w_target_equity"].clip(0.0, 1.0)
    b100 = pd.Series(1.00, index=dates)
    b60 = pd.Series(0.60, index=dates)
    b80 = pd.Series(0.80, index=dates)
    spx = data["sp_price"].astype(float).replace(0.0, np.nan).ffill()
    spx_log = np.log(spx)
    spx_min = float(spx_log.min())
    spx_max = float(spx_log.max())

    def x_pos(i: int) -> float:
        return left + i / max(len(dates) - 1, 1) * plot_w

    def y_pos(equity_weight: float) -> float:
        return top + plot_h - equity_weight * plot_h

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
        f'<text class="title" x="{left}" y="32">Udzial akcji w portfelu na tle S&amp;P 500</text>',
        f'<text class="small" x="{left}" y="56">Strategia vs benchmarki, {dates.min().date()} - {dates.max().date()}; SPX w skali log, znormalizowany do wysokosci wykresu</text>',
    ]

    for pct in np.arange(0.0, 1.01, 0.1):
        y = y_pos(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')
        lines.append(f'<text class="tick" x="{left + plot_w + 10}" y="{y + 4:.2f}">{1.0 - pct:.0%}</text>')

    year_ticks = pd.date_range(dates.min(), dates.max(), freq="5YS")
    for tick in year_ticks:
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_pos(idx)
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 44}" text-anchor="middle">{tick.year}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left + plot_w}" y1="{top}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Akcje</text>')
    lines.append(f'<text class="axis" transform="translate({width - 24} {top + plot_h / 2:.2f}) rotate(90)" text-anchor="middle">Obligacje / gotowka</text>')
    lines.append(
        f'<polyline fill="none" stroke="#8f8f88" stroke-width="2.2" opacity="0.42" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{points(dates, spx, x_pos, y_spx)}"/>'
    )

    series = [
        ("benchmark_100_equity", b100, "#3a0ca3", "Benchmark 100% akcji"),
        ("benchmark_80_20", b80, "#c1121f", "Benchmark 80/20"),
        ("benchmark_60_40", b60, "#6a994e", "Benchmark 60/40"),
        ("strategy", strategy, "#15616d", "Strategia"),
    ]
    for _, values, color, _ in series:
        stroke_width = 3.0 if color == "#15616d" else 2.4
        opacity = 1.0 if color == "#15616d" else 0.72
        dash = "" if color == "#15616d" else ' stroke-dasharray="8 7"'
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="{stroke_width}" opacity="{opacity}"{dash} '
            f'stroke-linejoin="round" stroke-linecap="round" points="{points(dates, values, x_pos, y_pos)}"/>'
        )

    legend_x, legend_y = left + 18, top + 22
    for i, (_, values, color, label) in enumerate(series[::-1]):
        y = legend_y + i * 25
        final = float(values.iloc[-1])
        dash = "" if label == "Strategia" else ' stroke-dasharray="8 7"'
        lines.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="4"{dash}/>')
        lines.append(f'<text class="small" x="{legend_x + 44}" y="{y + 5}">{label}: {final:.1%} akcji</text>')
    spx_y = legend_y + len(series) * 25
    lines.append(f'<line x1="{legend_x}" y1="{spx_y}" x2="{legend_x + 34}" y2="{spx_y}" stroke="#8f8f88" stroke-width="4" opacity="0.55"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{spx_y + 5}">S&amp;P 500: {spx.iloc[-1]:,.0f}</text>')

    min_date = strategy.idxmin()
    max_date = strategy.idxmax()
    for label, date in [("min", min_date), ("max", max_date), ("teraz", strategy.index[-1])]:
        idx = dates.get_loc(date)
        value = float(strategy.loc[date])
        x = x_pos(idx)
        y = y_pos(value)
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5.5" fill="#111" stroke="#fff" stroke-width="1.2"/>')
        lines.append(f'<text class="small" x="{x + 8:.2f}" y="{y - 8:.2f}">{label}: {value:.1%}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "allocation_percent.svg")
    print((REPORTS / "allocation_percent.svg").resolve())
    print(data[["w_target_equity"]].describe().to_string())


if __name__ == "__main__":
    main()
