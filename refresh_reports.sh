#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Odswiezam backtest i raporty..."

python strategy_backtest.py
python allocation_plot.py
python rates_unemployment_plot.py
python pe_hysteresis_plot.py
python spx_ndx_mix_plot.py
python gold_allocation_plot.py
python oil_allocation_plot.py
python bond_allocation_plot.py
python leverage_mode_plot.py
python yearly_allocation_report.py
python annual_heatmap_report.py
python decade_report.py
python underwater_report.py
python strategy_mix_report.py
python transaction_report.py
python bond_switch_report.py

echo
echo "Gotowe. Otworz report_view.html"
