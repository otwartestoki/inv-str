from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def points(dates: pd.DatetimeIndex, values: pd.Series, x_func, y_func) -> str:
    return " ".join(f"{x_func(i):.2f},{y_func(float(v)):.2f}" for i, v in enumerate(values))


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 560
    left, right, top, bottom = 82, 82, 62, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index
    oil_signal = data["oil_regime"].astype(float).fillna(0.0)
    oil_price = data["oil_price"].astype(float).replace(0.0, np.nan).ffill()
    oil_price = oil_price.where(oil_price > 0).ffill()
    oil_log = np.log(oil_price)
    oil_min = float(oil_log.min())
    oil_max = float(oil_log.max())

    def x_pos(i: int) -> float:
        return left + i / max(len(dates) - 1, 1) * plot_w

    def y_signal(value: float) -> float:
        return top + plot_h - value * plot_h

    def y_oil(value: float) -> float:
        if oil_max == oil_min or value <= 0 or np.isnan(value):
            return top + plot_h / 2
        scaled = (np.log(value) - oil_min) / (oil_max - oil_min)
        return top + plot_h - scaled * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Sygnał ropy na tle ceny WTI</text>',
        f'<text class="small" x="{left}" y="56">Ropa nie jest aktywem w portfelu; oil_regime ogranicza agresywne wejscie w obligacje 30+</text>',
    ]

    for pct in np.arange(0.0, 1.01, 0.25):
        y = y_signal(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')

    for tick in pd.date_range(dates.min(), dates.max(), freq="5YS"):
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_pos(idx)
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 38}" text-anchor="middle">{tick.year}</text>')

    active = data["oil_regime"].astype(bool)
    start_idx = None
    for i, is_active in enumerate(active):
        if is_active and start_idx is None:
            start_idx = i
        if start_idx is not None and (not is_active or i == len(active) - 1):
            end_idx = i if is_active and i == len(active) - 1 else i - 1
            x1 = x_pos(start_idx)
            x2 = x_pos(end_idx)
            lines.append(f'<rect x="{x1:.2f}" y="{top}" width="{max(x2 - x1, 1):.2f}" height="{plot_h}" fill="#d97706" opacity="0.08"/>')
            start_idx = None

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Oil regime</text>')

    lines.append(
        f'<polyline fill="none" stroke="#9ca3af" stroke-width="2.2" opacity="0.50" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{points(dates, oil_price.ffill(), x_pos, y_oil)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#111827" stroke-width="3.2" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{points(dates, oil_signal, x_pos, y_signal)}"/>'
    )

    legend_x, legend_y = left + 18, top + 24
    lines.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 34}" y2="{legend_y}" stroke="#111827" stroke-width="4"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 5}">Oil regime: {"aktywny" if bool(active.iloc[-1]) else "nieaktywny"}</text>')
    lines.append(f'<line x1="{legend_x}" y1="{legend_y + 26}" x2="{legend_x + 34}" y2="{legend_y + 26}" stroke="#9ca3af" stroke-width="4" opacity="0.55"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 31}">Cena ropy / USO w tle</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "oil_allocation.svg")
    print((REPORTS / "oil_allocation.svg").resolve())
    print(data[["oil_regime", "oil_strong_regime", "oil_momentum_26w"]].describe(include="all").to_string())


if __name__ == "__main__":
    main()
