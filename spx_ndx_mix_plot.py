from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def polyline(values: pd.Series, x_func, y_func) -> str:
    return " ".join(f"{x_func(i):.2f},{y_func(float(v)):.2f}" for i, v in enumerate(values))


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 620
    left, right, top, bottom = 82, 42, 62, 76
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index

    equity = data["w_us_equity"] + data["w_world_equity"] + data["w_tech_equity"]
    ndx_share = (data["w_tech_equity"] / equity.replace(0.0, np.nan)).fillna(0.0).clip(0.0, 1.0)

    def x_pos(i: int) -> float:
        return left + i / max(len(dates) - 1, 1) * plot_w

    def y_pos(value: float) -> float:
        return top + plot_h - value * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Proporcja SPX / NDX w czesci akcyjnej</text>',
        f'<text class="small" x="{left}" y="56">Jedna linia pokazuje udzial NDX w czesci akcyjnej: 0% = calosc SPX, 50% = 50/50, 100% = calosc NDX</text>',
    ]

    for pct in np.arange(0.0, 1.01, 0.1):
        y = y_pos(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')

    year_ticks = pd.date_range(dates.min(), dates.max(), freq="5YS")
    for tick in year_ticks:
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_pos(idx)
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 42}" text-anchor="middle">{tick.year}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Udzial NDX w czesci akcyjnej</text>')
    for pct, label in [(0.0, "SPX"), (0.5, "50/50"), (1.0, "NDX")]:
        y = y_pos(float(pct))
        lines.append(f'<text class="small" x="{left + plot_w + 8}" y="{y + 4:.2f}" fill="#555">{label}</text>')

    lines.append(
        f'<polyline fill="none" stroke="#073b3a" stroke-width="3.8" stroke-linejoin="round" '
        f'stroke-linecap="round" points="{polyline(ndx_share, x_pos, y_pos)}"/>'
    )

    legend_x, legend_y = left + 18, top + 24
    lines.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 34}" y2="{legend_y}" stroke="#073b3a" stroke-width="4"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 5}">NDX w czesci akcyjnej: {ndx_share.iloc[-1]:.1%}; SPX: {1.0 - ndx_share.iloc[-1]:.1%}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "spx_ndx_mix.svg")
    equity = data["w_us_equity"] + data["w_world_equity"] + data["w_tech_equity"]
    mix = pd.DataFrame(
        {
            "spx_share_of_equity": data["w_us_equity"] / equity.replace(0.0, np.nan),
            "ndx_share_of_equity": data["w_tech_equity"] / equity.replace(0.0, np.nan),
        },
        index=data.index,
    ).fillna(0.0)
    mix.to_csv(REPORTS / "spx_ndx_mix.csv", index_label="date")
    print((REPORTS / "spx_ndx_mix.svg").resolve())
    print(mix.tail(12).to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
