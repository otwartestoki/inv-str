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


def regime_spans(active: pd.Series, x_values: np.ndarray, top: int, plot_h: int) -> list[str]:
    spans = []
    in_span = False
    start_x = 0.0
    values = active.fillna(False).astype(bool).to_numpy()
    for i, is_active in enumerate(values):
        if is_active and not in_span:
            in_span = True
            start_x = x_values[i]
        is_last = i == len(values) - 1
        if in_span and ((not is_active) or is_last):
            end_i = i if is_active and is_last else max(i - 1, 0)
            end_x = x_values[end_i]
            width = max(1.0, end_x - start_x)
            spans.append(
                f'<rect x="{start_x:.2f}" y="{top}" width="{width:.2f}" height="{plot_h}" '
                'fill="#f4b183" opacity="0.16"/>'
            )
            in_span = False
    return spans


def write_svg(data: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 700
    left, right, top, bottom = 86, 44, 64, 82
    plot_w = width - left - right
    plot_h = height - top - bottom
    dates = data.index
    x_values = np.linspace(left, left + plot_w, len(dates))

    exposure = pd.DataFrame(
        {
            "strategy": data[["w_us_equity", "w_world_equity", "w_tech_equity"]].sum(axis=1),
            "recommended": data[["w_us_equity", "w_world_equity", "w_tech_equity"]].sum(axis=1) * 0.30
            + data[["med_aggr_w_us_equity", "med_aggr_w_world_equity", "med_aggr_w_tech_equity"]].sum(axis=1) * 0.70,
            "medium": data[["med_aggr_w_us_equity", "med_aggr_w_world_equity", "med_aggr_w_tech_equity"]].sum(axis=1),
            "aggressive": data[["aggr_w_us_equity", "aggr_w_world_equity", "aggr_w_tech_equity"]].sum(axis=1),
        },
        index=dates,
    ).clip(lower=0.0)
    spx = data["sp_price"].astype(float).replace(0.0, np.nan).ffill()
    spx_log = np.log(spx)
    spx_min = float(spx_log.min())
    spx_max = float(spx_log.max())
    max_exposure = max(1.2, float(exposure.max().max()))
    y_max = np.ceil(max_exposure * 10.0) / 10.0

    def y_exp(value: float) -> float:
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
        f'<text class="title" x="{left}" y="32">Aktywacja trybu lewarowanego</text>',
        f'<text class="small" x="{left}" y="56">Ekspozycja akcyjna strategii; tlo pokazuje okresy, gdy rekomendowany miks przekracza 100% ekspozycji</text>',
    ]

    lines.extend(regime_spans(exposure["recommended"] > 1.0, x_values, top, plot_h))

    for value in np.arange(0.0, y_max + 0.001, 0.25):
        y = y_exp(float(value))
        stroke = "#b94a48" if abs(value - 1.0) < 1e-9 else "#deded8"
        width_line = 1.8 if abs(value - 1.0) < 1e-9 else 1.0
        dash = ' stroke-dasharray="8 6"' if abs(value - 1.0) < 1e-9 else ""
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="{stroke}" stroke-width="{width_line}"{dash}/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{value:.0%}</text>')

    for tick in pd.date_range(dates.min(), dates.max(), freq="5YS"):
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x = x_values[idx]
            lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x:.2f}" y="{height - 46}" text-anchor="middle">{tick.year}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="axis" transform="translate(24 {top + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle">Ekspozycja akcyjna</text>')

    lines.append(
        f'<polyline fill="none" stroke="#8f8f88" stroke-width="2.0" opacity="0.36" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{points(spx, x_values, y_spx)}"/>'
    )

    series = [
        ("strategy", "#073b3a", 3.7, 1.0, "Bazowa"),
        ("recommended", "#0b6e4f", 3.6, 1.0, "Rekomendowany miks"),
        ("medium", "#b45f06", 3.0, 0.9, "Srednio agresywna"),
        ("aggressive", "#7a1f1f", 2.2, 0.22, "Agresywna / tryb ekstremalny"),
    ]
    for key, color, stroke_width, opacity, _ in series:
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="{stroke_width}" '
            f'opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round" '
            f'points="{points(exposure[key], x_values, y_exp)}"/>'
        )

    legend_x, legend_y = left + 18, top + 24
    for i, (key, color, stroke_width, opacity, label) in enumerate(series):
        y = legend_y + i * 25
        final = float(exposure[key].iloc[-1])
        lines.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="{stroke_width + 0.7}" opacity="{opacity}"/>')
        lines.append(f'<text class="small" x="{legend_x + 44}" y="{y + 5}">{label}: {final:.1%}</text>')
    spx_y = legend_y + len(series) * 25
    lines.append(f'<line x1="{legend_x}" y1="{spx_y}" x2="{legend_x + 34}" y2="{spx_y}" stroke="#8f8f88" stroke-width="4" opacity="0.45"/>')
    lines.append(f'<text class="small" x="{legend_x + 44}" y="{spx_y + 5}">S&amp;P 500 w tle: {spx.iloc[-1]:,.0f}</text>')
    threshold_y = y_exp(1.0)
    lines.append(f'<text class="small" x="{left + plot_w - 4}" y="{threshold_y - 8:.2f}" text-anchor="end" fill="#8a2f2f">prog lewara 100%</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")

    out = exposure.copy()
    out["recommended_leverage_mode"] = exposure["recommended"] > 1.0
    out["medium_leverage_mode"] = exposure["medium"] > 1.0
    out["aggressive_leverage_mode"] = exposure["aggressive"] > 1.0
    out.to_csv(REPORTS / "leverage_mode.csv", index_label="date", float_format="%.8f")


def main() -> None:
    data = pd.read_csv(REPORTS / "weekly_backtest.csv", parse_dates=["date"]).set_index("date")
    write_svg(data, REPORTS / "leverage_mode.svg")
    mode = pd.read_csv(REPORTS / "leverage_mode.csv", parse_dates=["date"])
    print((REPORTS / "leverage_mode.svg").resolve())
    print(mode.tail(12).to_string(index=False))


if __name__ == "__main__":
    main()
