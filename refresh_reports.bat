@echo off
setlocal

cd /d "%~dp0"

echo Odswiezam backtest i raporty...

python .\strategy_backtest.py || goto :error
python .\allocation_plot.py || goto :error
python .\rates_unemployment_plot.py || goto :error
python .\pe_hysteresis_plot.py || goto :error
python .\spx_ndx_mix_plot.py || goto :error
python .\gold_allocation_plot.py || goto :error
python .\oil_allocation_plot.py || goto :error
python .\bond_allocation_plot.py || goto :error
python .\leverage_mode_plot.py || goto :error
python .\yearly_allocation_report.py || goto :error
python .\annual_heatmap_report.py || goto :error
python .\decade_report.py || goto :error
python .\underwater_report.py || goto :error
python .\strategy_mix_report.py || goto :error
python .\leverage_realism_report.py || goto :error
python .\transaction_report.py || goto :error
python .\bond_switch_report.py || goto :error

echo.
echo Gotowe. Otworz report_view.html
exit /b 0

:error
echo.
echo Blad odswiezania raportow.
exit /b 1
