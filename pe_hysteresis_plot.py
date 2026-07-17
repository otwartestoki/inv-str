from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def rising_bond_weight(pe: float) -> float:
    if pe <= 20.0:
        equity = 0.90
    elif pe >= 37.0:
        equity = 0.10
    else:
        equity = 0.90 - (pe - 20.0) / 17.0 * 0.80
    bond = 1.0 - equity
    return float(np.clip(bond, 0.10, 0.90))


def falling_bond_weight(pe: float) -> float:
    if pe <= 10.0:
        equity = 0.90
    elif pe >= 27.0:
        equity = 0.10
    else:
        equity = 0.90 - (pe - 10.0) / 17.0 * 0.80
    bond = 1.0 - equity
    return float(np.clip(bond, 0.10, 0.90))


def load_monthly_points() -> pd.DataFrame:
    signals = pd.read_csv(REPORTS / "signals.csv", parse_dates=["date"]).set_index("date")
    cols = ["forward_pe_proxy", "s3_equity", "s3_bond", "pe_branch"]
    for optional in ["s3_raw_equity", "s3_raw_bond"]:
        if optional in signals.columns:
            cols.append(optional)
    monthly = signals[cols].resample("ME").last().dropna()
    monthly.to_csv(REPORTS / "pe_hysteresis_monthly_points.csv", index_label="date")
    return monthly


def line_points(xs: np.ndarray, ys: np.ndarray, x_func, y_func) -> str:
    return " ".join(f"{x_func(float(x)):.2f},{y_func(float(y)):.2f}" for x, y in zip(xs, ys))


def write_svg(monthly: pd.DataFrame, path: Path) -> None:
    width, height = 1180, 760
    left, right, top, bottom = 84, 86, 70, 82
    plot_w = width - left - right
    plot_h = height - top - bottom

    x_min = max(5.0, math.floor(monthly["forward_pe_proxy"].min() / 5.0) * 5.0 - 5.0)
    x_max = min(60.0, math.ceil(monthly["forward_pe_proxy"].max() / 5.0) * 5.0 + 5.0)
    x_min = min(x_min, 10.0)
    x_max = max(x_max, 40.0)
    y_min, y_max = 0.0, 1.0

    def x_pos(pe: float) -> float:
        return left + (pe - x_min) / (x_max - x_min) * plot_w

    def y_pos(bond_weight: float) -> float:
        return top + plot_h - (bond_weight - y_min) / (y_max - y_min) * plot_h

    pe_grid = np.linspace(x_min, x_max, 360)
    rising = np.array([rising_bond_weight(v) for v in pe_grid])
    falling = np.array([falling_bond_weight(v) for v in pe_grid])
    path_points = line_points(monthly["forward_pe_proxy"].values, monthly["s3_bond"].values, x_pos, y_pos)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.small{font-size:13px}.tick{font-size:12px;fill:#555}.axis{font-size:14px;font-weight:600}</style>',
        f'<text class="title" x="{left}" y="32">Miesieczny ruch po krzywej histerezy P/E</text>',
        f'<text class="small" x="{left}" y="56">Punkty miesieczne: {monthly.index.min().date()} - {monthly.index.max().date()}</text>',
    ]

    for pe in np.arange(math.ceil(x_min / 5.0) * 5.0, x_max + 0.1, 5.0):
        x = x_pos(float(pe))
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#ecece6" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 48}" text-anchor="middle">{pe:.0f}</text>')

    for pct in np.arange(0.0, 1.01, 0.1):
        y = y_pos(float(pct))
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{pct:.0%}</text>')
        lines.append(f'<text class="tick" x="{left + plot_w + 10}" y="{y + 4:.2f}">{1.0 - pct:.0%}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left + plot_w}" y1="{top}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" x="{left + plot_w / 2:.2f}" y="{height - 18}" text-anchor="middle">Forward P/E proxy</text>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Udzial obligacji</text>')
    lines.append(f'<text class="axis" transform="translate({width - 24} {top + plot_h / 2:.2f}) rotate(90)" text-anchor="middle">Udzial akcji</text>')

    lines.append(
        f'<polyline fill="none" stroke="#c1121f" stroke-width="2.8" opacity="0.72" '
        f'points="{line_points(pe_grid, rising, x_pos, y_pos)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#15616d" stroke-width="2.8" opacity="0.72" '
        f'points="{line_points(pe_grid, falling, x_pos, y_pos)}"/>'
    )
    lines.append(
        f'<polyline fill="none" stroke="#2f2f2f" stroke-width="1.8" opacity="0.38" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{path_points}"/>'
    )

    n = len(monthly)
    for i, (_, row) in enumerate(monthly.iterrows()):
        age = i / max(n - 1, 1)
        r = int(72 + age * 160)
        g = int(96 + age * 34)
        b = int(170 - age * 110)
        radius = 2.4 + age * 2.2
        lines.append(
            f'<circle cx="{x_pos(row.forward_pe_proxy):.2f}" cy="{y_pos(row.s3_bond):.2f}" '
            f'r="{radius:.2f}" fill="rgb({r},{g},{b})" fill-opacity="0.72" stroke="#fff" stroke-width="0.4"/>'
        )

    first = monthly.iloc[0]
    last = monthly.iloc[-1]
    for label, row, dy in [("start", first, -12), ("teraz", last, -12)]:
        x = x_pos(float(row.forward_pe_proxy))
        y = y_pos(float(row.s3_bond))
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="#111" stroke="#fff" stroke-width="1.5"/>')
        lines.append(
            f'<text class="small" x="{x + 10:.2f}" y="{y + dy:.2f}">{label}: '
            f'P/E {row.forward_pe_proxy:.1f}, obligacje {row.s3_bond:.0%}, akcje {row.s3_equity:.0%}</text>'
        )

    legend_x, legend_y = left + 18, top + 22
    lines.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 34}" y2="{legend_y}" stroke="#c1121f" stroke-width="3"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 5}">galaz: P/E rosnie</text>')
    lines.append(f'<line x1="{legend_x}" y1="{legend_y + 24}" x2="{legend_x + 34}" y2="{legend_y + 24}" stroke="#15616d" stroke-width="3"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 29}">galaz: P/E spada</text>')
    lines.append(f'<line x1="{legend_x}" y1="{legend_y + 48}" x2="{legend_x + 34}" y2="{legend_y + 48}" stroke="#2f2f2f" stroke-width="2" opacity="0.45"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{legend_y + 53}">sciezka miesieczna</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    monthly = load_monthly_points()
    write_svg(monthly, REPORTS / "pe_hysteresis_path.svg")
    print((REPORTS / "pe_hysteresis_path.svg").resolve())
    print(monthly.tail(12).to_string())


if __name__ == "__main__":
    main()
