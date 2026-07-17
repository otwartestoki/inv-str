from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def points(values: pd.Series, x_values: np.ndarray, y_func) -> str:
    coords = []
    for x, value in zip(x_values, values):
        if pd.isna(value):
            continue
        coords.append(f"{x:.2f},{y_func(float(value)):.2f}")
    return " ".join(coords)


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 680
    left, right, top, bottom = 86, 86, 62, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index
    x_values = np.linspace(left, left + plot_w, len(dates))

    bond_sleeve = (data["w_long_bond"] + data["w_floating_bond"]).replace(0.0, np.nan)
    long_share = (data["w_long_bond"] / bond_sleeve).fillna(0.0).clip(0.0, 1.0)

    def y_weight(value: float) -> float:
        return top + plot_h - value * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Proporcja obligacje 30+ / zmiennoprocentowe</text>',
        f'<text class="small" x="{left}" y="56">Jedna linia pokazuje udzial obligacji 30+ w czesci defensywnej: 0% = floating/gotowka, 50% = pol na pol, 100% = calosc 30+</text>',
    ]

    for pct in np.arange(0.0, 1.01, 0.1):
        y = y_weight(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')

    for tick in pd.date_range(dates.min(), dates.max(), freq="5YS"):
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_values[idx]
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 44}" text-anchor="middle">{tick.year}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Udzial obligacji 30+ w czesci defensywnej</text>')
    for pct, label in [(0.0, "Floating"), (0.5, "50/50"), (1.0, "30+")]:
        y = y_weight(float(pct))
        lines.append(f'<text class="small" x="{left + plot_w + 8}" y="{y + 4:.2f}" fill="#555">{label}</text>')

    lines.append(
        f'<polyline fill="none" stroke="#073b3a" stroke-width="3.8" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{points(long_share, x_values, y_weight)}"/>'
    )

    legend_x, legend_y = left + 18, top + 22
    lines.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 34}" y2="{legend_y}" stroke="#073b3a" stroke-width="4"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 5}">Obligacje 30+: {long_share.iloc[-1]:.1%}; floating/gotowka: {1.0 - long_share.iloc[-1]:.1%}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "bond_allocation_macro.svg")
    bond_sleeve = (data["w_long_bond"] + data["w_floating_bond"]).replace(0.0, np.nan)
    mix = pd.DataFrame(
        {
            "long_bond_share_of_defensive": data["w_long_bond"] / bond_sleeve,
            "floating_share_of_defensive": data["w_floating_bond"] / bond_sleeve,
            "total_bond_cash_weight": data["w_long_bond"] + data["w_floating_bond"],
        },
        index=data.index,
    ).fillna(0.0)
    mix.to_csv(REPORTS / "bond_allocation_mix.csv", index_label="date")
    print((REPORTS / "bond_allocation_macro.svg").resolve())
    print(mix.tail(12).to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
