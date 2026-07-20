from __future__ import annotations

import io
import html
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

START = os.environ.get("BACKTEST_START", "1954-07-02")
END = pd.Timestamp(os.environ.get("BACKTEST_END", pd.Timestamp.today().date().isoformat())).normalize()
TRADING_COST = 0.002


FRED_SERIES = {
    "fed_funds": "FEDFUNDS",
    "unemployment": "UNRATE",
    "cpi": "CPIAUCSL",
    "real_gdp": "GDPC1",
    "dgs10": "DGS10",
    "oil_price": "DCOILWTICO",
}

OPTIONAL_FRED_SERIES = {}
if os.environ.get("FRED_GOLD_SERIES_ID"):
    OPTIONAL_FRED_SERIES["gold_price"] = os.environ["FRED_GOLD_SERIES_ID"]

YAHOO_SYMBOLS = {
    "us_equity": "SPY",
    "world_equity": "ACWI",
    "tech_equity": "QQQ",
    "gold": "GLD",
    "long_bond_etf": "TLT",
}


@dataclass
class BacktestResult:
    weekly: pd.DataFrame
    signals: pd.DataFrame
    allocations: pd.DataFrame
    returns: pd.DataFrame
    metrics: pd.Series


def ensure_dirs() -> None:
    for path in (RAW, PROCESSED, REPORTS):
        path.mkdir(parents=True, exist_ok=True)


def download(url: str, dest: Path, max_age_days: int = 14) -> bytes:
    force = os.environ.get("FORCE_DOWNLOAD", "").lower() in {"1", "true", "yes"}
    if dest.exists() and not force:
        age_days = (time.time() - dest.stat().st_mtime) / 86400
        if age_days <= max_age_days and dest.stat().st_size > 0:
            return dest.read_bytes()

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 inv-str research backtest",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    dest.write_bytes(data)
    return data


def fred_csv(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    data = download(url, RAW / f"fred_{series_id}.csv")
    df = pd.read_csv(io.BytesIO(data))
    df.columns = ["date", series_id]
    df["date"] = pd.to_datetime(df["date"])
    values = pd.to_numeric(df[series_id].replace(".", np.nan), errors="coerce")
    return pd.Series(values.values, index=df["date"], name=series_id).dropna()


def yahoo_adj_close(symbol: str) -> pd.Series:
    start_epoch = int(pd.Timestamp("1900-01-01", tz="UTC").timestamp())
    end_epoch = int((END + pd.Timedelta(days=3)).tz_localize("UTC").timestamp())
    encoded = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start_epoch}&period2={end_epoch}&interval=1d&events=history"
    )
    data = download(url, RAW / f"yahoo_{symbol.replace('^', '')}.json")
    payload = json.loads(data.decode("utf-8"))
    result = payload["chart"]["result"][0]
    idx = pd.to_datetime(result["timestamp"], unit="s").tz_localize("UTC").tz_convert(None).normalize()
    quote = result["indicators"]["quote"][0]
    close = pd.Series(quote["close"], index=idx, name=symbol).astype(float)
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose")
    if adj is not None:
        close = pd.Series(adj, index=idx, name=symbol).astype(float)
    return close.dropna()


def shiller_data() -> pd.DataFrame:
    url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
    data = download(url, RAW / "shiller_ie_data.xls", max_age_days=30)
    try:
        raw = pd.read_excel(io.BytesIO(data), sheet_name="Data", header=None)
    except ImportError as exc:
        raise RuntimeError(
            "Brakuje pakietu do czytania XLS. Zainstaluj: python -m pip install xlrd"
        ) from exc

    header_row = raw.index[raw.iloc[:, 0].astype(str).str.strip().eq("Date")]
    if len(header_row) == 0:
        raise RuntimeError("Nie znalazlem naglowka w pliku Shillera.")
    start = int(header_row[0]) + 1
    data = raw.iloc[start:, :15].copy()
    data.columns = [
        "decimal_date",
        "sp_price",
        "dividend",
        "earnings",
        "cpi",
        "date_fraction",
        "long_rate",
        "real_price",
        "real_dividend",
        "real_total_return_price",
        "real_earnings",
        "scaled_earnings",
        "cape",
        "blank",
        "tr_cape",
    ]
    data = data[pd.to_numeric(data["decimal_date"], errors="coerce").notna()]
    year = np.floor(data["decimal_date"].astype(float)).astype(int)
    month = ((data["decimal_date"].astype(float) - year) * 100).round().astype(int)
    month = month.clip(1, 12)
    data.index = pd.to_datetime({"year": year, "month": month, "day": 1})
    cols = ["sp_price", "dividend", "earnings", "cpi", "long_rate", "real_total_return_price", "cape", "tr_cape"]
    return data[cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")


def local_gold_price() -> pd.Series | None:
    path = RAW / "gold_price.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    normalized = {col.lower().strip(): col for col in df.columns}
    date_col = normalized.get("date")
    price_col = normalized.get("price") or normalized.get("gold") or normalized.get("close")
    if date_col is None or price_col is None:
        raise RuntimeError("data/raw/gold_price.csv musi miec kolumny date oraz price/gold/close.")
    idx = pd.to_datetime(df[date_col])
    values = pd.to_numeric(df[price_col], errors="coerce")
    return pd.Series(values.values, index=idx, name="gold_price").dropna()


def local_oil_price() -> pd.Series | None:
    path = RAW / "oil_price.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    normalized = {col.lower().strip(): col for col in df.columns}
    date_col = normalized.get("date")
    price_col = normalized.get("price") or normalized.get("oil") or normalized.get("close")
    if date_col is None or price_col is None:
        raise RuntimeError("data/raw/oil_price.csv musi miec kolumny date oraz price/oil/close.")
    idx = pd.to_datetime(df[date_col])
    values = pd.to_numeric(df[price_col], errors="coerce")
    return pd.Series(values.values, index=idx, name="oil_price").dropna()


def weekly_last(series: pd.Series, weeks: pd.DatetimeIndex) -> pd.Series:
    return series.sort_index().reindex(weeks, method="ffill")


def weekly_returns_from_price(price: pd.Series, weeks: pd.DatetimeIndex) -> pd.Series:
    weekly_price = price.sort_index().resample("W-FRI").last().reindex(weeks, method="ffill")
    return weekly_price.pct_change().fillna(0.0)


def shiller_monthly_total_return(shiller: pd.DataFrame) -> pd.Series:
    price = shiller["sp_price"].astype(float)
    dividend_yield_month = (shiller["dividend"].astype(float) / 12.0) / price.shift(1)
    return price.pct_change().add(dividend_yield_month, fill_value=0.0).fillna(0.0)


def distribute_monthly_to_weekly(monthly_return: pd.Series, weeks: pd.DatetimeIndex) -> pd.Series:
    out = pd.Series(0.0, index=weeks)
    month_periods = weeks.to_period("M")
    monthly = monthly_return.copy()
    monthly.index = monthly.index.to_period("M")
    for period, idx in pd.Series(weeks, index=weeks).groupby(month_periods).groups.items():
        if period in monthly.index:
            n = len(idx)
            out.loc[idx] = (1.0 + float(monthly.loc[period])) ** (1.0 / n) - 1.0
    return out


def synthetic_bond_returns(dgs10: pd.Series, fed_funds: pd.Series, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    y10 = weekly_last(dgs10, weeks).astype(float) / 100.0
    fed = weekly_last(fed_funds, weeks).astype(float) / 100.0
    dy = y10.diff().fillna(0.0)
    fixed = (y10.shift(1).fillna(y10) / 52.0) - 7.0 * dy
    long_fixed = (y10.shift(1).fillna(y10) / 52.0) - 16.0 * dy
    floating = fed.shift(1).fillna(fed) / 52.0
    return pd.DataFrame({"fixed_bond": fixed, "long_bond": long_fixed, "floating_bond": floating}, index=weeks)


def extend_shiller_with_market_price(
    shiller: pd.DataFrame,
    weeks: pd.DatetimeIndex,
    market_price: pd.Series | None,
) -> pd.DataFrame:
    out = pd.DataFrame(index=weeks)
    out["cape"] = weekly_last(shiller["cape"].dropna(), weeks)
    out["sp_price"] = weekly_last(shiller["sp_price"].dropna(), weeks)
    out["earnings"] = weekly_last(shiller["earnings"].dropna(), weeks)

    if market_price is None or market_price.dropna().empty:
        return out

    weekly_market = market_price.sort_index().resample("W-FRI").last().reindex(weeks, method="ffill")
    last_month = shiller[["cape", "sp_price"]].dropna().index.max()
    base_candidates = weeks[weeks >= last_month]
    if pd.isna(last_month) or len(base_candidates) == 0:
        return out

    base_week = base_candidates[0]
    base_market = weekly_market.loc[base_week]
    if pd.isna(base_market) or base_market == 0:
        return out

    extend_mask = weeks > base_week
    price_ratio = weekly_market.loc[extend_mask] / base_market
    if price_ratio.dropna().empty:
        return out

    base_sp = out.loc[base_week, "sp_price"]
    base_cape = out.loc[base_week, "cape"]
    out.loc[extend_mask, "sp_price"] = base_sp * price_ratio
    out.loc[extend_mask, "cape"] = base_cape * price_ratio
    return out


def build_panel() -> pd.DataFrame:
    shiller = shiller_data()
    fred = {name: fred_csv(series_id) for name, series_id in FRED_SERIES.items()}
    for name, series_id in OPTIONAL_FRED_SERIES.items():
        try:
            fred[name] = fred_csv(series_id)
        except Exception as exc:
            print(f"UWAGA: nie pobrano opcjonalnej serii FRED {series_id}: {exc}", file=sys.stderr)
    fred["dgs10"] = fred["dgs10"].combine_first(shiller["long_rate"].dropna())
    yahoo = {}
    for name, symbol in YAHOO_SYMBOLS.items():
        try:
            yahoo[name] = yahoo_adj_close(symbol)
        except Exception as exc:
            print(f"UWAGA: nie pobrano {symbol}: {exc}", file=sys.stderr)

    weeks = pd.date_range(START, END, freq="W-FRI")
    panel = pd.DataFrame(index=weeks)

    shiller_total_weekly = distribute_monthly_to_weekly(shiller_monthly_total_return(shiller), weeks)
    panel["us_equity_ret"] = shiller_total_weekly
    if "us_equity" in yahoo:
        real = weekly_returns_from_price(yahoo["us_equity"], weeks)
        panel.loc[real.index[real.index >= real[real.ne(0)].index.min()], "us_equity_ret"] = real

    panel["world_equity_ret"] = panel["us_equity_ret"] * 0.85
    if "world_equity" in yahoo:
        real = weekly_returns_from_price(yahoo["world_equity"], weeks)
        first = real[real.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "world_equity_ret"] = real.loc[panel.index >= first]

    panel["tech_equity_ret"] = (panel["us_equity_ret"] * 1.25).clip(-0.18, 0.18)
    if "tech_equity" in yahoo:
        real = weekly_returns_from_price(yahoo["tech_equity"], weeks)
        first = real[real.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "tech_equity_ret"] = real.loc[panel.index >= first]

    panel["gold_ret"] = 0.0
    panel["gold_available"] = False
    local_gold = local_gold_price()
    if local_gold is not None:
        local_gold_ret = weekly_returns_from_price(local_gold, weeks)
        first = local_gold_ret[local_gold_ret.ne(0)].index.min()
        if pd.notna(first):
            first = max(first, pd.Timestamp("1971-01-01"))
            panel.loc[panel.index >= first, "gold_ret"] = local_gold_ret.loc[panel.index >= first]
            panel.loc[panel.index >= first, "gold_available"] = True
    if "gold_price" in fred:
        fred_gold = weekly_returns_from_price(fred["gold_price"], weeks)
        first = fred_gold[fred_gold.ne(0)].index.min()
        if pd.notna(first):
            first = max(first, pd.Timestamp("1971-01-01"))
            panel.loc[panel.index >= first, "gold_ret"] = fred_gold.loc[panel.index >= first]
            panel.loc[panel.index >= first, "gold_available"] = True
    if "gold" in yahoo:
        real = weekly_returns_from_price(yahoo["gold"], weeks)
        first = real[real.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "gold_ret"] = real.loc[panel.index >= first]
            panel.loc[panel.index >= first, "gold_available"] = True

    panel["oil_ret"] = 0.0
    panel["oil_available"] = False
    panel["oil_price"] = np.nan
    local_oil = local_oil_price()
    if local_oil is not None:
        local_oil_weekly = weekly_last(local_oil, weeks)
        local_oil_ret = weekly_returns_from_price(local_oil, weeks)
        first = local_oil_ret[local_oil_ret.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "oil_price"] = local_oil_weekly.loc[panel.index >= first]
            panel.loc[panel.index >= first, "oil_ret"] = local_oil_ret.loc[panel.index >= first]
            panel.loc[panel.index >= first, "oil_available"] = True
    if "oil_price" in fred:
        fred_oil_weekly = weekly_last(fred["oil_price"], weeks)
        fred_oil_ret = weekly_returns_from_price(fred["oil_price"], weeks).clip(lower=-0.60, upper=1.50)
        first = fred_oil_ret[fred_oil_ret.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "oil_price"] = fred_oil_weekly.loc[panel.index >= first]
            panel.loc[panel.index >= first, "oil_ret"] = fred_oil_ret.loc[panel.index >= first]
            panel.loc[panel.index >= first, "oil_available"] = True
    if "oil" in yahoo:
        oil_price = yahoo["oil"].sort_index().resample("W-FRI").last().reindex(weeks, method="ffill")
        real = weekly_returns_from_price(yahoo["oil"], weeks)
        first = real[real.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "oil_ret"] = real.loc[panel.index >= first]
            panel.loc[panel.index >= first, "oil_available"] = True
            panel.loc[panel.index >= first, "oil_price"] = panel.loc[panel.index >= first, "oil_price"].combine_first(
                oil_price.loc[panel.index >= first]
            )

    bonds = synthetic_bond_returns(fred["dgs10"], fred["fed_funds"], weeks)
    panel = panel.join(bonds)
    if "long_bond_etf" in yahoo:
        real = weekly_returns_from_price(yahoo["long_bond_etf"], weeks)
        first = real[real.ne(0)].index.min()
        if pd.notna(first):
            panel.loc[panel.index >= first, "long_bond"] = real.loc[panel.index >= first]

    for name, series in fred.items():
        panel[name] = weekly_last(series, weeks)
    shiller_weekly = extend_shiller_with_market_price(shiller, weeks, yahoo.get("us_equity"))
    panel["cape"] = shiller_weekly["cape"]
    panel["sp_price"] = shiller_weekly["sp_price"]
    panel["earnings"] = shiller_weekly["earnings"]

    eps_growth = panel["earnings"].replace(0, np.nan).pct_change(52)
    trend = eps_growth.rolling(156, min_periods=52).median().clip(-0.15, 0.18).fillna(0.04)
    forward_eps = panel["earnings"] * (1.0 + trend)
    panel["forward_pe_proxy"] = (panel["sp_price"] / forward_eps.replace(0, np.nan)).clip(5, 60)
    panel["data_quality"] = np.select(
        [
            panel.index < pd.Timestamp("1971-01-01"),
            panel.index < pd.Timestamp("1985-01-01"),
        ],
        ["medium_proxy_pre_1971", "medium_proxy_1971_1984"],
        default="high_1985_plus",
    )

    panel.to_csv(PROCESSED / "weekly_panel.csv", index_label="date")
    return panel.dropna(subset=["cape", "fed_funds", "unemployment", "real_gdp", "forward_pe_proxy"])


def shiller_signal(panel: pd.DataFrame) -> pd.Series:
    cape_m = panel["cape"].dropna().resample("MS").last()
    diff_24 = cape_m - cape_m.shift(24)
    smooth = diff_24.rolling(2, min_periods=1).mean()
    weekly = smooth.reindex(panel.index, method="ffill")
    return pd.Series(np.where(weekly < -6.0, 0.20, 0.80), index=panel.index, name="s1_equity")


def cycle_signals(panel: pd.DataFrame, s1_equity: pd.Series) -> pd.DataFrame:
    fed = panel["fed_funds"]
    unrate = panel["unemployment"]
    cpi_yoy = panel["cpi"].pct_change(52) * 100.0
    real_10y = panel["dgs10"] - cpi_yoy
    gdp_yoy = panel["real_gdp"].pct_change(52) * 100.0
    gdp_mom = panel["real_gdp"].pct_change() * 100.0
    sp_drawdown = panel["sp_price"] / panel["sp_price"].cummax() - 1.0
    unemployment_26w_change = unrate.diff(26)
    fed_26w_change = fed.diff(26)
    sp_above_ma40 = panel["sp_price"] > panel["sp_price"].rolling(40, min_periods=20).mean()
    oil_price = panel["oil_price"].replace(0, np.nan)
    oil_momentum_26w = oil_price.pct_change(26) * 100.0
    oil_above_ma40 = oil_price > oil_price.rolling(40, min_periods=20).mean()
    demand_recession_risk = (gdp_yoy < 0.0) | (unemployment_26w_change > 0.75)
    inflation_tightening_regime = (
        (cpi_yoy > 4.0)
        & (fed_26w_change > 0.75)
        & (panel["dgs10"].diff(26) > 0.50)
    )
    oil_regime = (
        panel["oil_available"].astype(bool)
        & oil_above_ma40
        & (oil_momentum_26w > 10.0)
        & (cpi_yoy > 3.5)
        & (unemployment_26w_change <= 0.50)
        & (~demand_recession_risk)
    )
    oil_strong_regime = oil_regime & (cpi_yoy > 6.0) & (real_10y < 0.0)
    stagflation_regime = (
        (cpi_yoy > 6.0)
        & ((gdp_yoy < 1.0) | (unemployment_26w_change > 0.0))
    )
    confirmed_expansion_regime = (
        (gdp_yoy > 2.0)
        & (gdp_mom >= 0.0)
        & (unemployment_26w_change <= 0.0)
        & (cpi_yoy < 4.0)
        & (fed_26w_change <= 0.75)
        & (sp_above_ma40 | (sp_drawdown > -0.08))
        & (~inflation_tightening_regime)
        & (~stagflation_regime)
    )
    soft_landing_candidate = (
        (gdp_yoy > 2.0)
        & (gdp_mom >= 0.0)
        & (unemployment_26w_change <= 0.0)
        & (cpi_yoy < 3.5)
        & (fed_26w_change <= 0.75)
        & (sp_above_ma40 | (sp_drawdown > -0.10))
        & (~inflation_tightening_regime)
    )

    bear_cross = (
        (fed.shift(1) > unrate.shift(1))
        & (fed <= unrate)
        & (fed.diff(13) < 0)
        & (unrate.diff(13) > 0)
    )
    shiller_buy_weekly = s1_equity >= 0.80
    shiller_fallback_stress = (gdp_yoy < 1.0) | (unemployment_26w_change >= 0.75) | (sp_drawdown <= -0.15)

    defensive = False
    defensive_weeks_left = 0
    reentry_ramp_week = None
    reentry_trigger = ""
    soft_landing_weeks = 0
    gdp_reentry_boost_weeks_left = 0
    long_bond_share_state = 0.0
    long_bond_share_weeks_since_change = 4
    gold_active_state = False
    gold_hold_weeks = 0
    equity = []
    reentry = []
    gdp_reentry_boost = []
    soft_landing_reentry = []
    soft_landing_regime = []
    long_bond_share = []
    gold = []
    bottom = []

    for date in panel.index:
        i = panel.index.get_loc(date)
        if bool(bear_cross.iloc[i]):
            defensive = True
            defensive_weeks_left = 52
            reentry_ramp_week = None
            reentry_trigger = ""
            soft_landing_weeks = 0
            gdp_reentry_boost_weeks_left = 0
        if defensive_weeks_left > 0:
            defensive_weeks_left -= 1

        gdp_reentry_signal = defensive and defensive_weeks_left == 0 and gdp_mom.iloc[i] < 0
        if defensive and defensive_weeks_left == 0 and bool(soft_landing_candidate.iloc[i]):
            soft_landing_weeks += 1
        elif reentry_ramp_week is None:
            soft_landing_weeks = 0
        soft_landing_reentry_signal = defensive and defensive_weeks_left == 0 and soft_landing_weeks >= 13
        shiller_reentry_signal = (
            defensive
            and defensive_weeks_left == 0
            and bool(shiller_buy_weekly.iloc[i])
            and bool(shiller_fallback_stress.iloc[i])
        )
        if defensive and reentry_ramp_week is None:
            if bool(gdp_reentry_signal):
                reentry_ramp_week = 0
                reentry_trigger = "gdp_mom_negative"
                gdp_reentry_boost_weeks_left = 52
            elif bool(soft_landing_reentry_signal):
                reentry_ramp_week = 0
                reentry_trigger = "soft_landing"
            elif bool(shiller_reentry_signal):
                reentry_ramp_week = 0
                reentry_trigger = "shiller_fallback"

        if defensive and reentry_ramp_week is not None:
            tranche = min(6, 1 + reentry_ramp_week // 4)
            cycle_equity = 0.80 * tranche / 6.0
            reentry_ramp_week += 1
            if reentry_ramp_week >= 24:
                defensive = False
                reentry_ramp_week = None
                reentry_trigger = ""
                soft_landing_weeks = 0
        else:
            cycle_equity = 0.00 if defensive else 0.80

        fed_13w_change = fed.diff(13).iloc[i]
        dgs10_13w_change = panel["dgs10"].diff(13).iloc[i]
        fed_falling = fed_13w_change < -0.25
        fed_plateau = fed.iloc[i] >= 4.0 and fed_13w_change <= 0.10
        inflation_after_peak = cpi_yoy.iloc[i] < cpi_yoy.rolling(26, min_periods=10).max().iloc[i] - 0.20
        inflation_cooling_13w = cpi_yoy.diff(13).iloc[i] <= 0.0
        inflation_reaccelerating = cpi_yoy.diff(13).iloc[i] > 0.25 and cpi_yoy.iloc[i] > 3.0
        aggressive_hiking = fed_13w_change > 0.50
        yield_spike = dgs10_13w_change > 0.75
        high_nominal_rates = fed.iloc[i] >= 4.00 or panel["dgs10"].iloc[i] >= 4.25
        very_high_rates = fed.iloc[i] >= 5.00 or panel["dgs10"].iloc[i] >= 4.75 or real_10y.iloc[i] >= 1.50
        weak_growth = gdp_yoy.iloc[i] < 1.50 or unemployment_26w_change.iloc[i] > 0.0
        duration_anticipation = (
            high_nominal_rates
            and bool(inflation_after_peak or inflation_cooling_13w)
            and not bool(aggressive_hiking)
            and not bool(inflation_reaccelerating)
            and not bool(yield_spike and not inflation_after_peak)
        )

        duration_score = 0
        duration_score += int(bool(high_nominal_rates))
        duration_score += int(bool(very_high_rates))
        duration_score += int(bool(real_10y.iloc[i] >= 1.00))
        duration_score += int(bool(fed_plateau))
        duration_score += int(bool(fed_falling))
        duration_score += int(bool(inflation_after_peak))
        duration_score += int(bool(dgs10_13w_change < -0.25))
        duration_score -= int(bool(aggressive_hiking))
        duration_score -= int(bool(inflation_reaccelerating))
        duration_score -= int(bool(yield_spike and not inflation_after_peak))
        duration_score -= int(bool(inflation_tightening_regime.iloc[i]))
        duration_score -= int(bool(stagflation_regime.iloc[i] and not inflation_after_peak))

        if duration_score <= 1:
            target_long_share = 0.0
        elif duration_score == 2:
            target_long_share = 0.25
        elif duration_score == 3:
            target_long_share = 0.50
        elif duration_score == 4:
            target_long_share = 0.75
        else:
            target_long_share = 0.75
        if bool(high_nominal_rates and not aggressive_hiking and not yield_spike):
            target_long_share = max(target_long_share, 0.25)
        if bool(duration_anticipation):
            target_long_share = max(target_long_share, 0.50)
        if bool(duration_anticipation and (weak_growth or real_10y.iloc[i] >= 0.75 or fed_plateau)):
            target_long_share = max(target_long_share, 0.75)
        if bool(duration_anticipation and very_high_rates and weak_growth and inflation_after_peak):
            target_long_share = max(target_long_share, 0.75)
        if bool(fed.iloc[i] < 2.0 and panel["dgs10"].iloc[i] < 3.0):
            target_long_share = 0.0
        if bool(inflation_tightening_regime.iloc[i] and not inflation_after_peak):
            target_long_share = min(target_long_share, 0.25)
        if bool(stagflation_regime.iloc[i] and not inflation_after_peak):
            target_long_share = min(target_long_share, 0.25)

        long_bond_share_weeks_since_change += 1
        share_diff = target_long_share - long_bond_share_state
        change_wait = 4 if share_diff > 0 else 8
        if long_bond_share_weeks_since_change >= change_wait and abs(share_diff) >= 0.25:
            long_bond_share_state += float(np.clip(share_diff, -0.25, 0.25))
            long_bond_share_state = float(np.clip(long_bond_share_state, 0.0, 1.0))
            long_bond_share_weeks_since_change = 0

        gold_available = bool(panel["gold_available"].iloc[i]) if "gold_available" in panel else True
        first_hike_after_low = gold_available and fed.shift(13).iloc[i] < 1.50 and fed.diff(13).iloc[i] > 0.25
        stagflation_gold_signal = gold_available and bool(stagflation_regime.iloc[i])
        if bool(first_hike_after_low or stagflation_gold_signal):
            gold_active_state = True
            gold_hold_weeks = 0

        if gold_active_state:
            gold_hold_weeks += 1

        inflation_controlled = cpi_yoy.rolling(26, min_periods=13).max().iloc[i] < 3.0
        real_rates_positive = real_10y.rolling(26, min_periods=13).min().iloc[i] > 1.0
        fed_not_hiking = fed.diff(26).iloc[i] <= 0.25
        shiller_risk_on = s1_equity.iloc[i] >= 0.80
        min_gold_hold_done = gold_hold_weeks >= 104
        if bool(gold_active_state and min_gold_hold_done and inflation_controlled and real_rates_positive and fed_not_hiking and shiller_risk_on):
            gold_active_state = False

        gold_active = gold_active_state

        gdp_bottom = gdp_yoy.diff(52).iloc[i] < 0 and gdp_yoy.diff(13).iloc[i] > 0
        shiller_buy = s1_equity.iloc[i] >= 0.80
        bottom_signal = bool(gdp_bottom or shiller_buy)

        equity.append(cycle_equity)
        reentry.append(reentry_trigger)
        gdp_reentry_boost.append(gdp_reentry_boost_weeks_left > 0)
        soft_landing_reentry.append(bool(soft_landing_reentry_signal))
        soft_landing_regime.append(bool(soft_landing_candidate.iloc[i]))
        long_bond_share.append(float(long_bond_share_state))
        gold.append(bool(gold_active))
        bottom.append(bottom_signal)
        if gdp_reentry_boost_weeks_left > 0:
            gdp_reentry_boost_weeks_left -= 1

    return pd.DataFrame(
        {
            "s2_equity": equity,
            "cycle_reentry_trigger": reentry,
            "gdp_reentry_boost": gdp_reentry_boost,
            "soft_landing_reentry": soft_landing_reentry,
            "soft_landing_regime": soft_landing_regime,
            "fixed_bond_mode": pd.Series(long_bond_share, index=panel.index) >= 0.50,
            "long_bond_share": long_bond_share,
            "gold_mode": gold,
            "bottom_tilt": bottom,
            "fed_unemployment_bear_cross": bear_cross.fillna(False),
            "cpi_yoy": cpi_yoy,
            "real_10y": real_10y,
            "gdp_yoy": gdp_yoy,
            "gdp_mom": gdp_mom,
            "sp_drawdown": sp_drawdown,
            "unemployment_26w_change": unemployment_26w_change,
            "shiller_fallback_stress": shiller_fallback_stress.fillna(False),
            "inflation_tightening_regime": inflation_tightening_regime.fillna(False),
            "stagflation_regime": stagflation_regime.fillna(False),
            "confirmed_expansion_regime": confirmed_expansion_regime.fillna(False),
            "oil_regime": oil_regime.fillna(False),
            "oil_strong_regime": oil_strong_regime.fillna(False),
            "oil_momentum_26w": oil_momentum_26w,
        },
        index=panel.index,
    )


def pe_hysteresis_signal(panel: pd.DataFrame) -> pd.DataFrame:
    pe = panel["forward_pe_proxy"].rolling(4, min_periods=1).mean()
    branch = "rising"
    held_bond = None
    raw_bond_weights = []
    bond_weights = []
    branches = []

    for value in pe:
        if branch == "rising" and value >= 37.0:
            branch = "falling"
        elif branch == "falling" and value <= 10.0:
            branch = "rising"

        if branch == "rising":
            if value <= 20.0:
                equity = 0.90
            elif value >= 37.0:
                equity = 0.10
            else:
                equity = 0.90 - (value - 20.0) / 17.0 * 0.80
        else:
            if value <= 10.0:
                equity = 0.90
            elif value >= 27.0:
                equity = 0.10
            else:
                equity = 0.90 - (value - 10.0) / 17.0 * 0.80

        bond = 1.0 - equity

        raw_bond = float(np.clip(bond, 0.10, 0.90))
        if held_bond is None:
            held_bond = raw_bond
        elif abs(raw_bond - held_bond) >= 0.05:
            held_bond = raw_bond

        raw_bond_weights.append(raw_bond)
        bond_weights.append(float(held_bond))
        branches.append(branch)

    bond_series = pd.Series(bond_weights, index=panel.index, name="s3_bond")
    raw_bond_series = pd.Series(raw_bond_weights, index=panel.index, name="s3_raw_bond")
    return pd.DataFrame(
        {
            "s3_equity": 1.0 - bond_series,
            "s3_bond": bond_series,
            "s3_raw_equity": 1.0 - raw_bond_series,
            "s3_raw_bond": raw_bond_series,
            "pe_branch": branches,
            "forward_pe_proxy": pe,
        },
        index=panel.index,
    )


def build_allocations(panel: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    s3_adjusted = signals["s3_equity"].copy()
    s3_adjusted.loc[signals["gdp_reentry_boost"].astype(bool)] = s3_adjusted.loc[
        signals["gdp_reentry_boost"].astype(bool)
    ].clip(lower=0.40)
    base_equity = pd.concat([signals["s1_equity"], signals["s2_equity"]], axis=1).mean(axis=1).clip(0.0, 0.90)
    target_equity = pd.concat([signals["s1_equity"], signals["s2_equity"], s3_adjusted], axis=1).mean(axis=1)

    confirmed_expansion = (
        signals["confirmed_expansion_regime"].astype(bool)
        & (signals["s1_equity"] >= 0.80)
        & (signals["s2_equity"] >= 0.80)
    )
    target_equity.loc[confirmed_expansion] = target_equity.loc[confirmed_expansion].clip(lower=0.90)

    macro_cap = pd.Series(0.90, index=panel.index, name="macro_cap")
    macro_cap.loc[signals["inflation_tightening_regime"].astype(bool)] = 0.65
    stagflation = signals["stagflation_regime"].astype(bool)
    macro_cap.loc[stagflation] = macro_cap.loc[stagflation].clip(upper=0.55)
    recovery_boost = (
        signals["gdp_reentry_boost"].astype(bool)
        & (signals["sp_drawdown"] <= -0.08)
        & (~signals["inflation_tightening_regime"].astype(bool))
        & (~signals["stagflation_regime"].astype(bool))
    )
    recovery_floor = pd.Series(0.0, index=panel.index)
    recovery_floor.loc[recovery_boost] = 0.70
    recovery_floor.loc[recovery_boost & (signals["sp_drawdown"] <= -0.12)] = 0.75
    recovery_floor.loc[recovery_boost & (signals["sp_drawdown"] <= -0.18)] = 0.80
    recovery_floor.loc[recovery_boost & (signals["sp_drawdown"] <= -0.25)] = 0.85
    recovery_floor.loc[recovery_boost & (signals["sp_drawdown"] <= -0.35)] = 0.90
    target_equity = pd.concat([target_equity, recovery_floor], axis=1).max(axis=1)
    target_equity = pd.concat([target_equity, macro_cap], axis=1).min(axis=1).clip(0.0, 0.90)
    alloc = pd.DataFrame(
        0.0,
        index=panel.index,
        columns=["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"],
    )
    tech_phase = "late"
    tech_phase_weeks = 0
    for date in panel.index:
        i = panel.index.get_loc(date)
        eq = float(target_equity.loc[date])
        bond = 1.0 - eq

        if i > 0:
            prev_date = panel.index[i - 1]
            equity_jump = target_equity.loc[date] - target_equity.loc[prev_date]
            cycle_reentry = signals.loc[prev_date, "s2_equity"] < 0.80 and signals.loc[date, "s2_equity"] >= 0.80
            reentry_start = (
                signals.loc[date, "cycle_reentry_trigger"] != ""
                and signals.loc[prev_date, "cycle_reentry_trigger"] == ""
            )
            if equity_jump >= 0.15 or bool(cycle_reentry) or bool(reentry_start):
                tech_phase = "early"
                tech_phase_weeks = 0

        gdp_recovering = signals.loc[date, "gdp_yoy"] > 0 and signals["gdp_yoy"].diff(26).iloc[i] > 0
        unemployment_improving = panel["unemployment"].diff(26).iloc[i] <= 0
        tightening_cycle = panel["fed_funds"].diff(26).iloc[i] > 0.50
        inflation_pressure = signals.loc[date, "cpi_yoy"] > 3.5 and panel["fed_funds"].diff(26).iloc[i] > 0

        if tech_phase == "early" and tech_phase_weeks >= 26 and bool(gdp_recovering and unemployment_improving):
            tech_phase = "mid"
            tech_phase_weeks = 0
        elif tech_phase == "mid" and bool(tightening_cycle or inflation_pressure):
            tech_phase = "late"
            tech_phase_weeks = 0

        valuation_tech_risk = (
            (signals.loc[date, "s1_equity"] < 0.80)
            or (
                signals.loc[date, "forward_pe_proxy"] > 25.0
                and signals.loc[date, "s3_equity"] < 0.65
            )
        )
        if tech_phase != "late" and bool(valuation_tech_risk):
            tech_phase = "late"
            tech_phase_weeks = 0

        if bool(signals.loc[date, "inflation_tightening_regime"]):
            ndx_share = 0.0
        elif date < pd.Timestamp("1985-01-01"):
            if tech_phase == "early":
                ndx_share = 0.30
            elif tech_phase == "mid":
                ndx_share = 0.20
            else:
                ndx_share = 0.0
        elif tech_phase == "early":
            ndx_share = 0.80
        elif tech_phase == "mid":
            ndx_share = 0.50
        else:
            ndx_share = 0.0

        alloc.loc[date, "us_equity"] = eq * (1.0 - ndx_share)
        alloc.loc[date, "tech_equity"] = eq * ndx_share
        tech_phase_weeks += 1

        if bool(signals.loc[date, "gold_mode"]):
            gold_target = 0.15 if bool(signals.loc[date, "stagflation_regime"]) else 0.10
            gold = min(gold_target, bond)
            alloc.loc[date, "gold"] = gold
            bond -= gold

        long_share = float(signals.loc[date, "long_bond_share"])
        long_bond_weight = bond * long_share
        if bool(signals.loc[date, "oil_regime"]):
            defensive_total = bond + float(alloc.loc[date, "gold"])
            long_bond_weight = min(long_bond_weight, 0.25 * defensive_total)
        alloc.loc[date, "long_bond"] = long_bond_weight
        alloc.loc[date, "floating_bond"] = bond - long_bond_weight

    asset_cols = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
    rebalanced = alloc[asset_cols].copy()
    held = None
    weeks_since_rebalance = 999
    for date in alloc.index:
        target = alloc.loc[date, asset_cols]
        recovery_rebalance = bool(signals.loc[date, "cycle_reentry_trigger"] != "")
        if held is None:
            held = target.copy()
            weeks_since_rebalance = 0
        elif recovery_rebalance and (target - held).abs().max() > 1e-10:
            held = target.copy()
            weeks_since_rebalance = 0
        else:
            weeks_since_rebalance += 1
        max_drift = (target - held).abs().max()
        if weeks_since_rebalance >= 8 and max_drift >= 0.10:
            held = target.copy()
            weeks_since_rebalance = 0
        elif max_drift >= 0.20:
            held = target.copy()
            weeks_since_rebalance = 0
        rebalanced.loc[date, asset_cols] = held

    alloc[asset_cols] = rebalanced
    alloc["raw_target_equity"] = target_equity
    alloc["target_equity"] = alloc[["us_equity", "world_equity", "tech_equity"]].sum(axis=1)
    alloc["base_equity"] = base_equity
    alloc["pe_cap"] = macro_cap
    alloc["s3_equity_adjusted"] = s3_adjusted
    return alloc


def build_aggressive_allocations(
    panel: pd.DataFrame, signals: pd.DataFrame, base_allocations: pd.DataFrame, max_equity: float
) -> pd.DataFrame:
    asset_cols = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
    aggressive = base_allocations[asset_cols].copy()
    equity_cols = ["us_equity", "world_equity", "tech_equity"]
    defensive_cols = ["fixed_bond", "long_bond", "floating_bond", "gold"]

    sp_momentum_26w = panel["sp_price"].pct_change(26)
    sp_above_ma40 = panel["sp_price"] > panel["sp_price"].rolling(40, min_periods=20).mean()
    risk_ok = (
        (~signals["inflation_tightening_regime"].astype(bool))
        & (~signals["stagflation_regime"].astype(bool))
        & (~signals["oil_regime"].astype(bool))
    )
    expansion_momentum = (
        signals["confirmed_expansion_regime"].astype(bool)
        & risk_ok
        & sp_above_ma40.fillna(False)
        & (sp_momentum_26w > 0.03)
        & (signals["forward_pe_proxy"] < 35.0)
    )
    rebound_momentum = (
        signals["gdp_reentry_boost"].astype(bool)
        & risk_ok
        & sp_above_ma40.fillna(False)
        & (sp_momentum_26w > 0.0)
        & (signals["sp_drawdown"] <= -0.08)
    )

    target_equity = aggressive[equity_cols].sum(axis=1).copy()
    target_equity.loc[expansion_momentum] = target_equity.loc[expansion_momentum].clip(lower=max_equity)
    target_equity.loc[rebound_momentum] = target_equity.loc[rebound_momentum].clip(lower=max_equity)

    target_equity.loc[signals["inflation_tightening_regime"].astype(bool)] = target_equity.loc[
        signals["inflation_tightening_regime"].astype(bool)
    ].clip(upper=1.00)
    target_equity.loc[signals["stagflation_regime"].astype(bool)] = target_equity.loc[
        signals["stagflation_regime"].astype(bool)
    ].clip(upper=0.85)
    target_equity = target_equity.clip(0.0, max_equity)

    for date in aggressive.index:
        eq_now = float(aggressive.loc[date, equity_cols].sum())
        eq_target = float(target_equity.loc[date])
        if eq_now <= 0 or abs(eq_target - eq_now) < 1e-10:
            continue

        equity_mix = aggressive.loc[date, equity_cols] / eq_now
        if eq_target > eq_now:
            ndx_boost = 0.0
            if bool(rebound_momentum.loc[date]):
                ndx_boost = 0.50
            elif bool(expansion_momentum.loc[date]):
                ndx_boost = 0.25
            if ndx_boost > 0:
                equity_mix.loc["tech_equity"] = max(float(equity_mix.loc["tech_equity"]), ndx_boost)
                other = max(0.0, 1.0 - float(equity_mix.loc["tech_equity"]))
                non_tech_total = float(equity_mix[["us_equity", "world_equity"]].sum())
                if non_tech_total > 0:
                    equity_mix.loc[["us_equity", "world_equity"]] = (
                        equity_mix.loc[["us_equity", "world_equity"]] / non_tech_total * other
                    )
                else:
                    equity_mix.loc["us_equity"] = other

        aggressive.loc[date, equity_cols] = equity_mix * eq_target
        defensive_total = max(0.0, 1.0 - eq_target)
        old_defensive = aggressive.loc[date, defensive_cols]
        old_defensive_total = float(old_defensive.sum())
        if old_defensive_total > 0 and defensive_total > 0:
            aggressive.loc[date, defensive_cols] = old_defensive / old_defensive_total * defensive_total
        else:
            aggressive.loc[date, defensive_cols] = 0.0

    rebalanced = aggressive.copy()
    held = None
    weeks_since_rebalance = 999
    for date in aggressive.index:
        target = aggressive.loc[date, asset_cols]
        recovery_rebalance = bool(signals.loc[date, "cycle_reentry_trigger"] != "")
        if held is None:
            held = target.copy()
            weeks_since_rebalance = 0
        elif recovery_rebalance and (target - held).abs().max() > 1e-10:
            held = target.copy()
            weeks_since_rebalance = 0
        else:
            weeks_since_rebalance += 1
        max_drift = (target - held).abs().max()
        if weeks_since_rebalance >= 8 and max_drift >= 0.10:
            held = target.copy()
            weeks_since_rebalance = 0
        elif max_drift >= 0.25:
            held = target.copy()
            weeks_since_rebalance = 0
        rebalanced.loc[date, asset_cols] = held

    return rebalanced


def run_backtest(panel: pd.DataFrame) -> BacktestResult:
    s1 = shiller_signal(panel)
    s2 = cycle_signals(panel, s1)
    s3 = pe_hysteresis_signal(panel)
    signals = pd.concat([s1, s2, s3], axis=1)
    allocations = build_allocations(panel, signals)
    medium_aggressive_allocations = build_aggressive_allocations(panel, signals, allocations, max_equity=1.80)
    aggressive_allocations = build_aggressive_allocations(panel, signals, allocations, max_equity=3.30)

    asset_returns = panel[
        ["us_equity_ret", "world_equity_ret", "tech_equity_ret", "fixed_bond", "long_bond", "floating_bond", "gold_ret"]
    ].copy()
    asset_returns.columns = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]

    weights = allocations[asset_returns.columns].shift(1).fillna(allocations[asset_returns.columns].iloc[0])
    gross = (weights * asset_returns).sum(axis=1)
    turnover = allocations[asset_returns.columns].diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turnover * TRADING_COST

    medium_weights = medium_aggressive_allocations[asset_returns.columns].shift(1).fillna(
        medium_aggressive_allocations[asset_returns.columns].iloc[0]
    )
    medium_gross = (medium_weights * asset_returns).sum(axis=1)
    medium_turnover = medium_aggressive_allocations[asset_returns.columns].diff().abs().sum(axis=1).fillna(0.0)
    medium_leverage = medium_weights.sum(axis=1).clip(lower=1.0) - 1.0
    medium_financing_cost = medium_leverage * ((panel["fed_funds"].fillna(0.0) / 100.0 + 0.015) / 52.1775)
    medium_net = medium_gross - medium_turnover * TRADING_COST - medium_financing_cost

    aggressive_weights = aggressive_allocations[asset_returns.columns].shift(1).fillna(
        aggressive_allocations[asset_returns.columns].iloc[0]
    )
    aggressive_gross = (aggressive_weights * asset_returns).sum(axis=1)
    aggressive_turnover = aggressive_allocations[asset_returns.columns].diff().abs().sum(axis=1).fillna(0.0)
    leverage = aggressive_weights.sum(axis=1).clip(lower=1.0) - 1.0
    financing_cost = leverage * ((panel["fed_funds"].fillna(0.0) / 100.0 + 0.015) / 52.1775)
    aggressive_net = aggressive_gross - aggressive_turnover * TRADING_COST - financing_cost
    recommended_mix_net = 0.30 * net + 0.70 * medium_net
    benchmark_100_equity = asset_returns["us_equity"]
    benchmark_80_20 = 0.80 * asset_returns["us_equity"] + 0.20 * asset_returns["fixed_bond"]
    benchmark_60_40 = 0.60 * asset_returns["us_equity"] + 0.40 * asset_returns["fixed_bond"]

    returns = pd.DataFrame(
        {
            "strategy": net,
            "strategy_recommended_mix": recommended_mix_net,
            "strategy_medium_aggressive": medium_net,
            "strategy_aggressive": aggressive_net,
            "gross_strategy": gross,
            "gross_strategy_medium_aggressive": medium_gross,
            "gross_strategy_aggressive": aggressive_gross,
            "benchmark_100_equity": benchmark_100_equity,
            "benchmark_80_20": benchmark_80_20,
            "benchmark_60_40": benchmark_60_40,
            "turnover": turnover,
            "turnover_medium_aggressive": medium_turnover,
            "turnover_aggressive": aggressive_turnover,
            "medium_aggressive_leverage": medium_leverage,
            "aggressive_leverage": leverage,
            "medium_aggressive_financing_cost": medium_financing_cost,
            "aggressive_financing_cost": financing_cost,
        },
        index=panel.index,
    )
    weekly = pd.concat(
        [
            panel,
            signals,
            allocations.add_prefix("w_"),
            medium_aggressive_allocations.add_prefix("med_aggr_w_"),
            aggressive_allocations.add_prefix("aggr_w_"),
            returns,
        ],
        axis=1,
    )
    metrics = performance_metrics(
        returns[
            [
                "strategy",
                "strategy_recommended_mix",
                "strategy_medium_aggressive",
                "strategy_aggressive",
                "benchmark_100_equity",
                "benchmark_80_20",
                "benchmark_60_40",
            ]
        ]
    )
    return BacktestResult(weekly, signals, allocations, returns, metrics)


def performance_metrics(returns: pd.DataFrame) -> pd.Series:
    rows = {}
    for name, ret in returns.items():
        ret = ret.dropna()
        wealth = (1.0 + ret).cumprod()
        years = len(ret) / 52.1775
        cagr = wealth.iloc[-1] ** (1.0 / years) - 1.0
        vol = ret.std() * math.sqrt(52.1775)
        sharpe = cagr / vol if vol > 0 else np.nan
        drawdown = wealth / wealth.cummax() - 1.0
        rows[(name, "CAGR")] = cagr
        rows[(name, "Volatility")] = vol
        rows[(name, "Sharpe_0rf")] = sharpe
        rows[(name, "MaxDrawdown")] = drawdown.min()
        rows[(name, "FinalWealth")] = wealth.iloc[-1]
    return pd.Series(rows)


def write_reports(result: BacktestResult) -> None:
    result.weekly.to_csv(REPORTS / "weekly_backtest.csv", index_label="date")
    result.signals.to_csv(REPORTS / "signals.csv", index_label="date")
    result.allocations.to_csv(REPORTS / "allocations.csv", index_label="date")
    result.returns.to_csv(REPORTS / "returns.csv", index_label="date")
    asset_cols = ["us_equity", "world_equity", "tech_equity", "fixed_bond", "long_bond", "floating_bond", "gold"]
    latest_alloc = result.allocations.iloc[-1]
    latest_weekly = result.weekly.iloc[-1]

    def prefixed_weights(prefix: str) -> dict[str, float]:
        return {col: float(latest_weekly[f"{prefix}{col}"]) for col in asset_cols}

    base_weights = {col: float(latest_alloc[col]) for col in asset_cols}
    medium_weights = prefixed_weights("med_aggr_w_")
    aggressive_weights = prefixed_weights("aggr_w_")
    recommended_weights = {
        col: 0.30 * base_weights[col] + 0.70 * medium_weights[col]
        for col in asset_cols
    }
    latest_payload = {
        "date": str(result.allocations.index[-1].date()),
        "weights": base_weights,
        "strategies": {
            "strategy": {
                "label": "Strategia bazowa",
                "weights": base_weights,
            },
            "strategy_recommended_mix": {
                "label": "Rekomendowany miks 30/70/0",
                "weights": recommended_weights,
            },
            "strategy_medium_aggressive": {
                "label": "Strategia srednio agresywna",
                "weights": medium_weights,
            },
            "strategy_aggressive": {
                "label": "Strategia agresywna",
                "weights": aggressive_weights,
            },
        },
        "labels": {
            "us_equity": "SPX / akcje USA",
            "world_equity": "Akcje swiat",
            "tech_equity": "NDX / tech",
            "fixed_bond": "Obligacje stale",
            "long_bond": "Obligacje 30+",
            "floating_bond": "Floating / gotowka",
            "gold": "Zloto",
        },
    }
    (REPORTS / "latest_allocation.js").write_text(
        "window.INV_STR_LATEST_ALLOCATION = "
        + json.dumps(latest_payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    metrics = result.metrics.unstack(1)
    metrics.to_csv(REPORTS / "metrics.csv", float_format="%.6f")

    portfolio_cols = [
        "strategy",
        "strategy_recommended_mix",
        "strategy_medium_aggressive",
        "strategy_aggressive",
        "benchmark_100_equity",
        "benchmark_80_20",
        "benchmark_60_40",
    ]
    yearly = result.returns[portfolio_cols].resample("YE").apply(lambda x: (1 + x).prod() - 1)
    yearly.to_csv(REPORTS / "yearly_returns.csv", index_label="year")
    equity_100 = (1.0 + result.returns[portfolio_cols]).cumprod() * 100.0
    equity_100.to_csv(REPORTS / "equity_curve_100.csv", index_label="date")
    drawdown_100 = equity_100 / equity_100.cummax() - 1.0
    equity_payload = {
        "dates": [str(date.date()) for date in equity_100.index],
        "labels": {
            "strategy": "Strategia bazowa",
            "strategy_recommended_mix": "Rekomendowany miks 30/70/0",
            "strategy_medium_aggressive": "Strategia srednio agresywna",
            "strategy_aggressive": "Strategia agresywna",
            "benchmark_100_equity": "100% akcje",
            "benchmark_80_20": "80/20",
            "benchmark_60_40": "60/40",
        },
        "equity": {
            col: [round(float(value), 6) for value in equity_100[col]]
            for col in portfolio_cols
        },
        "drawdown": {
            col: [round(float(value), 8) for value in drawdown_100[col]]
            for col in portfolio_cols
        },
    }
    (REPORTS / "equity_curve_data.js").write_text(
        "window.INV_STR_EQUITY_CURVES = "
        + json.dumps(equity_payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    write_equity_svg(equity_100, REPORTS / "equity_curve_100.svg")
    write_equity_svg(equity_100, REPORTS / "equity_curve_100_log.svg", log_scale=True)

    def fmt_pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    def fmt_money(value: float) -> str:
        return f"{value:,.2f}"

    labels = {
        "strategy": "Strategia",
        "strategy_recommended_mix": "Rekomendowany miks 30/70/0",
        "strategy_medium_aggressive": "Strategia srednio agresywna",
        "strategy_aggressive": "Strategia agresywna",
        "benchmark_100_equity": "100% akcje",
        "benchmark_80_20": "80/20",
        "benchmark_60_40": "60/40",
    }
    ordered_rows = [
        "strategy",
        "strategy_recommended_mix",
        "strategy_medium_aggressive",
        "strategy_aggressive",
        "benchmark_100_equity",
        "benchmark_80_20",
        "benchmark_60_40",
    ]
    last_alloc = result.allocations.iloc[-1]
    last_signal = result.signals.iloc[-1]
    latest_date = result.allocations.index[-1].date()
    equity_weight = float(last_alloc[["us_equity", "world_equity", "tech_equity"]].sum())
    fixed_weight = float(last_alloc["fixed_bond"] + last_alloc["long_bond"])
    floating_weight = float(last_alloc["floating_bond"])
    gold_weight = float(last_alloc["gold"])
    bond_weight = max(0.0, 1.0 - equity_weight - gold_weight)
    duration_share = fixed_weight / (fixed_weight + floating_weight) if fixed_weight + floating_weight > 0 else 0.0
    panel_weights = {
        "Akcje": equity_weight,
        "Polskie obligacje nominalne": bond_weight / 2.0,
        "Polskie obligacje stale %": (bond_weight / 4.0) * duration_share,
        "Polskie obligacje zmienne %": (bond_weight / 4.0) * (1.0 - duration_share),
        "Zagraniczne obligacje stale %": (bond_weight / 4.0) * duration_share,
        "Zagraniczne obligacje zmienne %": (bond_weight / 4.0) * (1.0 - duration_share),
        "Zloto": gold_weight,
    }

    lines = ["# Glowne podsumowanie strategii", ""]
    lines.append(f"Okres backtestu: **{result.returns.index.min().date()} - {result.returns.index.max().date()}**")
    lines.append(f"Ostatni sygnal: **{latest_date}**")
    lines.append("")
    lines.append("## Najwazniejsze wnioski")
    strategy = metrics.loc["strategy"]
    equity_100_row = metrics.loc["benchmark_100_equity"]
    lines.append(
        f"- Strategia konczy z CAGR **{fmt_pct(strategy['CAGR'])}**, max drawdown **{fmt_pct(strategy['MaxDrawdown'])}** "
        f"i wartoscia koncowa **{fmt_money(strategy['FinalWealth'])}** z poczatkowych 1.00."
    )
    aggressive = metrics.loc["strategy_aggressive"]
    medium_aggressive = metrics.loc["strategy_medium_aggressive"]
    recommended_mix = metrics.loc["strategy_recommended_mix"]
    lines.append(
        f"- Rekomendowany miks 30/70/0 ma CAGR **{fmt_pct(recommended_mix['CAGR'])}** przy max drawdown "
        f"**{fmt_pct(recommended_mix['MaxDrawdown'])}**; to domyslny kompromis miedzy strategia bazowa i srednio agresywna."
    )
    lines.append(
        f"- Wariant srednio agresywny ma CAGR **{fmt_pct(medium_aggressive['CAGR'])}** przy max drawdown "
        f"**{fmt_pct(medium_aggressive['MaxDrawdown'])}**; uzywa tego samego filtra momentum, ale tylko do 180% ekspozycji."
    )
    lines.append(
        f"- Wariant agresywny ma CAGR **{fmt_pct(aggressive['CAGR'])}** przy max drawdown "
        f"**{fmt_pct(aggressive['MaxDrawdown'])}**; to test, a nie domyslny wariant rebalancingu."
    )
    lines.append(
        f"- 100% akcji ma podobny CAGR (**{fmt_pct(equity_100_row['CAGR'])}**), ale duzo glebszy max drawdown "
        f"(**{fmt_pct(equity_100_row['MaxDrawdown'])}**)."
    )
    lines.append(
        f"- Aktualnie strategia jest defensywna: akcje **{fmt_pct(equity_weight)}**, "
        f"obligacje/gotowka **{fmt_pct(bond_weight)}**, zloto **{fmt_pct(gold_weight)}**."
    )
    lines.append(
        f"- W czesci obligacyjnej sygnal duration wynosi **{fmt_pct(duration_share)}**: "
        "to oznacza czesciowe, ale nie pelne, wejscie w obligacje stale."
    )
    lines.append("")
    lines.append("## Wyniki")
    lines.append("| Portfel | CAGR | Max DD | Zmiennosc | Sharpe | Wartosc koncowa |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for key in ordered_rows:
        row = metrics.loc[key]
        lines.append(
            f"| {labels[key]} | {fmt_pct(row['CAGR'])} | {fmt_pct(row['MaxDrawdown'])} | "
            f"{fmt_pct(row['Volatility'])} | {row['Sharpe_0rf']:.2f} | {fmt_money(row['FinalWealth'])} |"
        )
    lines.append("")
    lines.append("## Aktualna alokacja modelu")
    lines.append("| Klasa | Udzial |")
    lines.append("|---|---:|")
    lines.append(f"| Akcje USA / SPX | {fmt_pct(float(last_alloc['us_equity']))} |")
    lines.append(f"| Akcje swiat | {fmt_pct(float(last_alloc['world_equity']))} |")
    lines.append(f"| Tech / NDX | {fmt_pct(float(last_alloc['tech_equity']))} |")
    lines.append(f"| Obligacje stale / 30+ | {fmt_pct(fixed_weight)} |")
    lines.append(f"| Obligacje zmienne / gotowka | {fmt_pct(floating_weight)} |")
    lines.append(f"| Zloto | {fmt_pct(gold_weight)} |")
    lines.append("")
    lines.append("## Praktyczny podzial do panelu rebalancingu")
    lines.append("| Pozycja | Cel |")
    lines.append("|---|---:|")
    for label, value in panel_weights.items():
        lines.append(f"| {label} | {fmt_pct(value)} |")
    lines.append("")
    lines.append("## Aktualne sygnaly makro")
    lines.append(f"- Shiller: **{fmt_pct(float(last_signal['s1_equity']))} akcji**")
    lines.append(f"- Cykl Fed/bezrobocie/PKB: **{fmt_pct(float(last_signal['s2_equity']))} akcji**")
    lines.append(f"- Forward P/E: **{fmt_pct(float(last_signal['s3_equity']))} akcji**")
    lines.append(f"- CPI YoY: **{float(last_signal['cpi_yoy']):.2f}%**")
    lines.append(f"- Real 10Y: **{float(last_signal['real_10y']):.2f}%**")
    lines.append(f"- GDP YoY: **{float(last_signal['gdp_yoy']):.2f}%**")
    lines.append(f"- Forward P/E proxy: **{float(last_signal['forward_pe_proxy']):.2f}**")
    lines.append("")
    lines.append("## Najwazniejsze raporty")
    lines.append("- [Kapital i drawdown - skala liniowa](equity_curve_100.svg)")
    lines.append("- [Kapital i drawdown - skala logarytmiczna](equity_curve_100_log.svg)")
    lines.append("- [Alokacja akcji na tle S&P 500](allocation_percent.svg)")
    lines.append("- [Obligacje stale/zmienne na tle makro](bond_allocation_macro.svg)")
    lines.append("- [Fed Funds vs bezrobocie](rates_vs_unemployment.svg)")
    lines.append("- [Histereza P/E](pe_hysteresis_path.svg)")
    lines.append("- [Proporcja SPX vs NDX](spx_ndx_mix.svg)")
    lines.append("- [Zloto](gold_allocation.svg)")
    lines.append("- [Ropa jako filtr makro](oil_allocation.svg)")
    lines.append("- [Aktywacja trybu lewarowanego](leverage_mode.svg)")
    lines.append("- [Porownanie dekadowe](decade_comparison.html)")
    lines.append("- [Czas pod woda](underwater_duration.html)")
    lines.append("- [Lista transakcji i rebalancing](transactions_rebalancing.html)")
    lines.append("")
    if "data_quality" in result.weekly:
        lines.append("## Jakosc danych")
        counts = result.weekly["data_quality"].value_counts().sort_index()
        for label, count in counts.items():
            lines.append(f"- {label}: {int(count)} tygodni")
        lines.append("")
    lines.append("## Uwagi")
    lines.append("- Forward P/E jest proxy bez look-ahead, nie oficjalna seria analityczna.")
    lines.append("- Okres przed 1985 wykorzystuje wiecej proxy niz nowszy fragment backtestu.")
    lines.append("- Wyniki przed startem ETF-ow sa czesciowo syntetyczne zgodnie z opisem w README.")
    lines.append("- Koszt transakcyjny: 0.2% od kazdej strony transakcji kupna/sprzedazy.")
    (REPORTS / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    metric_rows = []
    for key in ordered_rows:
        row = metrics.loc[key]
        metric_rows.append(
            "<tr>"
            f"<td>{html.escape(labels[key])}</td>"
            f"<td>{fmt_pct(row['CAGR'])}</td>"
            f"<td>{fmt_pct(row['MaxDrawdown'])}</td>"
            f"<td>{fmt_pct(row['Volatility'])}</td>"
            f"<td>{row['Sharpe_0rf']:.2f}</td>"
            f"<td>{fmt_money(row['FinalWealth'])}</td>"
            "</tr>"
        )
    model_rows = [
        ("Akcje USA / SPX", float(last_alloc["us_equity"])),
        ("Akcje swiat", float(last_alloc["world_equity"])),
        ("Tech / NDX", float(last_alloc["tech_equity"])),
        ("Obligacje stale / 30+", fixed_weight),
        ("Obligacje zmienne / gotowka", floating_weight),
        ("Zloto", gold_weight),
    ]
    panel_rows = list(panel_weights.items())
    signal_rows = [
        ("Shiller", f"{fmt_pct(float(last_signal['s1_equity']))} akcji"),
        ("Cykl Fed / bezrobocie / PKB", f"{fmt_pct(float(last_signal['s2_equity']))} akcji"),
        ("Forward P/E", f"{fmt_pct(float(last_signal['s3_equity']))} akcji"),
        ("CPI YoY", f"{float(last_signal['cpi_yoy']):.2f}%"),
        ("Real 10Y", f"{float(last_signal['real_10y']):.2f}%"),
        ("GDP YoY", f"{float(last_signal['gdp_yoy']):.2f}%"),
        ("Forward P/E proxy", f"{float(last_signal['forward_pe_proxy']):.2f}"),
    ]
    report_links = [
        ("Kapital i drawdown - skala liniowa", "equity_curve_100.svg"),
        ("Kapital i drawdown - skala logarytmiczna", "equity_curve_100_log.svg"),
        ("Alokacja akcji na tle S&P 500", "allocation_percent.svg"),
        ("Obligacje stale/zmienne na tle makro", "bond_allocation_macro.svg"),
        ("Fed Funds vs bezrobocie", "rates_vs_unemployment.svg"),
        ("Histereza P/E", "pe_hysteresis_path.svg"),
        ("Proporcja SPX vs NDX", "spx_ndx_mix.svg"),
        ("Zloto", "gold_allocation.svg"),
        ("Ropa jako filtr makro", "oil_allocation.svg"),
        ("Aktywacja trybu lewarowanego", "leverage_mode.svg"),
        ("Porownanie dekadowe", "decade_comparison.html"),
        ("Czas pod woda", "underwater_duration.html"),
        ("Lista transakcji i rebalancing", "transactions_rebalancing.html"),
    ]

    def html_table(rows: list[tuple[str, str]]) -> str:
        return "\n".join(
            f"<tr><td>{html.escape(str(label))}</td><td>{html.escape(str(value))}</td></tr>"
            for label, value in rows
        )

    summary_html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Glowne podsumowanie strategii</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #222; background: #fbfbf8; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }}
    .top-nav {{ margin-bottom: 18px; font-size: 14px; }}
    a {{ color: #15616d; font-weight: 650; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1 {{ margin: 0 0 6px; font-size: 30px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 0; color: #555; line-height: 1.45; }}
    .meta {{ margin-bottom: 22px; color: #666; }}
    .hero {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; margin: 22px 0; }}
    .metric {{ border: 1px solid #d8d1c3; background: #fff; padding: 14px; }}
    .metric span {{ display: block; color: #666; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 24px; }}
    section {{ margin-top: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid #d8d1c3; background: #fff; padding: 16px; }}
    ul {{ margin: 0; padding-left: 20px; color: #333; line-height: 1.55; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 8px 9px; border-bottom: 1px solid #e6e1d6; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1eee6; color: #333; }}
    .links {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 14px; }}
    .links li {{ margin: 0; }}
    @media (max-width: 760px) {{ .hero {{ grid-template-columns: 1fr 1fr; }} main {{ padding: 22px 14px 36px; }} }}
  </style>
</head>
<body>
  <main>
    <nav class="top-nav"><a href="../report_view.html">Backtest strategii</a> / Glowne podsumowanie</nav>
    <h1>Glowne podsumowanie strategii</h1>
    <p class="meta">Okres backtestu: <strong>{result.returns.index.min().date()} - {result.returns.index.max().date()}</strong> | Ostatni sygnal: <strong>{latest_date}</strong></p>

    <div class="hero">
      <div class="metric"><span>CAGR strategii</span><strong>{fmt_pct(strategy['CAGR'])}</strong></div>
      <div class="metric"><span>Max drawdown</span><strong>{fmt_pct(strategy['MaxDrawdown'])}</strong></div>
      <div class="metric"><span>Sharpe</span><strong>{strategy['Sharpe_0rf']:.2f}</strong></div>
      <div class="metric"><span>Wartosc koncowa</span><strong>{fmt_money(strategy['FinalWealth'])}</strong></div>
    </div>

    <section class="panel">
      <h2>Najwazniejsze wnioski</h2>
      <ul>
        <li>Strategia ma CAGR <strong>{fmt_pct(strategy['CAGR'])}</strong> przy max drawdown <strong>{fmt_pct(strategy['MaxDrawdown'])}</strong>.</li>
        <li>Rekomendowany miks 30/70/0 ma CAGR <strong>{fmt_pct(recommended_mix['CAGR'])}</strong> przy max drawdown <strong>{fmt_pct(recommended_mix['MaxDrawdown'])}</strong>; to domyslny kompromis miedzy baza i srednio agresywna.</li>
        <li>Wariant srednio agresywny ma CAGR <strong>{fmt_pct(medium_aggressive['CAGR'])}</strong> przy max drawdown <strong>{fmt_pct(medium_aggressive['MaxDrawdown'])}</strong>; to umiarkowana wersja filtra momentum do 180% ekspozycji.</li>
        <li>Wariant agresywny ma CAGR <strong>{fmt_pct(aggressive['CAGR'])}</strong> przy max drawdown <strong>{fmt_pct(aggressive['MaxDrawdown'])}</strong>; sluzy do sprawdzenia, ile ryzyka wymaga cel bliski 20% CAGR.</li>
        <li>100% akcji ma podobny CAGR (<strong>{fmt_pct(equity_100_row['CAGR'])}</strong>), ale drawdown jest duzo glebszy (<strong>{fmt_pct(equity_100_row['MaxDrawdown'])}</strong>).</li>
        <li>Aktualnie strategia jest defensywna: akcje <strong>{fmt_pct(equity_weight)}</strong>, obligacje/gotowka <strong>{fmt_pct(bond_weight)}</strong>, zloto <strong>{fmt_pct(gold_weight)}</strong>.</li>
        <li>Sygnal duration w czesci obligacyjnej wynosi <strong>{fmt_pct(duration_share)}</strong>, czyli model jest czesciowo w obligacjach stalych.</li>
      </ul>
    </section>

    <section>
      <h2>Wyniki</h2>
      <table>
        <thead><tr><th>Portfel</th><th>CAGR</th><th>Max DD</th><th>Zmiennosc</th><th>Sharpe</th><th>Wartosc koncowa</th></tr></thead>
        <tbody>{''.join(metric_rows)}</tbody>
      </table>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Aktualna alokacja modelu</h2>
        <table><tbody>{html_table([(label, fmt_pct(value)) for label, value in model_rows])}</tbody></table>
      </div>
      <div class="panel">
        <h2>Podzial do rebalancingu</h2>
        <table><tbody>{html_table([(label, fmt_pct(value)) for label, value in panel_rows])}</tbody></table>
      </div>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Aktualne sygnaly makro</h2>
        <table><tbody>{html_table(signal_rows)}</tbody></table>
      </div>
      <div class="panel">
        <h2>Uwagi</h2>
        <ul>
          <li>Forward P/E jest proxy bez look-ahead, nie oficjalna seria analityczna.</li>
          <li>Okres przed 1985 wykorzystuje wiecej proxy niz nowszy fragment backtestu.</li>
          <li>Koszt transakcyjny: 0.2% od kazdej strony kupna/sprzedazy.</li>
        </ul>
      </div>
    </section>

    <section>
      <h2>Najwazniejsze raporty</h2>
      <ul class="links">
        {''.join(f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>' for label, href in report_links)}
      </ul>
    </section>
  </main>
</body>
</html>
"""
    (REPORTS / "summary.html").write_text(summary_html, encoding="utf-8")


def write_equity_svg(equity: pd.DataFrame, path: Path, log_scale: bool = False) -> None:
    width, height = 1280, 860
    left, right, top, bottom = 86, 34, 54, 76
    plot_w = width - left - right
    equity_h = 480
    gap = 62
    drawdown_top = top + equity_h + gap
    drawdown_h = height - drawdown_top - bottom
    colors = {
        "strategy": "#073b3a",
        "strategy_recommended_mix": "#0b6e4f",
        "strategy_medium_aggressive": "#b45f06",
        "strategy_aggressive": "#7a1f1f",
        "benchmark_100_equity": "#b7a6e8",
        "benchmark_80_20": "#e7a7a2",
        "benchmark_60_40": "#b8d4a8",
    }
    stroke_widths = {
        "strategy": 4.2,
        "strategy_recommended_mix": 3.9,
        "strategy_medium_aggressive": 3.3,
        "strategy_aggressive": 3.5,
        "benchmark_100_equity": 2.2,
        "benchmark_80_20": 2.2,
        "benchmark_60_40": 2.2,
    }
    drawdown_widths = {
        "strategy": 3.2,
        "strategy_recommended_mix": 3.0,
        "strategy_medium_aggressive": 2.5,
        "strategy_aggressive": 2.6,
        "benchmark_100_equity": 1.8,
        "benchmark_80_20": 1.8,
        "benchmark_60_40": 1.8,
    }
    opacities = {
        "strategy": 1.0,
        "strategy_recommended_mix": 0.98,
        "strategy_medium_aggressive": 0.92,
        "strategy_aggressive": 0.90,
        "benchmark_100_equity": 0.72,
        "benchmark_80_20": 0.72,
        "benchmark_60_40": 0.72,
    }
    labels = {
        "strategy": "Strategia",
        "strategy_recommended_mix": "Rekomendowany miks 30/70/0",
        "strategy_medium_aggressive": "Strategia srednio agresywna",
        "strategy_aggressive": "Strategia agresywna",
        "benchmark_100_equity": "Benchmark 100% akcje",
        "benchmark_80_20": "Benchmark 80/20",
        "benchmark_60_40": "Benchmark 60/40",
    }
    equity = equity.dropna()
    drawdown = equity / equity.cummax() - 1.0
    max_y = float(equity.max().max())
    min_y = max(float(equity.min().min()), 1.0)
    if log_scale:
        y_min = 10.0 ** math.floor(math.log10(min_y))
        y_max = 10.0 ** math.ceil(math.log10(max_y))
    else:
        y_max = math.ceil(max_y / 1000.0) * 1000.0
        if y_max <= 0:
            y_max = 100.0
    dd_min = min(float(drawdown.min().min()), -0.05)
    dd_floor = math.floor(dd_min * 10.0) / 10.0

    dates = equity.index
    x_values = np.linspace(left, left + plot_w, len(dates))

    def y_equity(value: float) -> float:
        if log_scale:
            return top + equity_h - (math.log10(value) - math.log10(y_min)) / (math.log10(y_max) - math.log10(y_min)) * equity_h
        return top + equity_h - (value / y_max) * equity_h

    def y_drawdown(value: float) -> float:
        return drawdown_top + (value / dd_floor) * drawdown_h

    def path_points(series: pd.Series, y_func) -> str:
        coords = []
        for x_pos, value in zip(x_values, series.values):
            coords.append(f"{x_pos:.2f},{y_func(float(value)):.2f}")
        return " ".join(coords)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222} .small{font-size:13px}.tick{font-size:12px;fill:#555}.title{font-size:24px;font-weight:700}</style>',
        f'<text class="title" x="{left}" y="30">Wzrost inwestycji 100 USD i drawdown</text>',
        f'<text class="small" x="{left}" y="56">Okres {dates.min().date()} - {dates.max().date()}, skala {"logarytmiczna" if log_scale else "liniowa"}</text>',
    ]

    if log_scale:
        tick_values = []
        value = y_min
        while value <= y_max * 1.001:
            tick_values.append(value)
            value *= 10.0
    else:
        tick_values = [y_max * i / 5 for i in range(6)]
    for value in tick_values:
        y_pos = y_equity(value)
        lines.append(f'<line x1="{left}" y1="{y_pos:.2f}" x2="{left + plot_w}" y2="{y_pos:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y_pos + 4:.2f}" text-anchor="end">${value:,.0f}</text>')

    year_ticks = pd.date_range(dates.min(), dates.max(), freq="5YS")
    for tick in year_ticks:
        idx = dates.searchsorted(tick)
        if 0 <= idx < len(dates):
            x_pos = x_values[idx]
            lines.append(f'<line x1="{x_pos:.2f}" y1="{top}" x2="{x_pos:.2f}" y2="{top + equity_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<line x1="{x_pos:.2f}" y1="{drawdown_top}" x2="{x_pos:.2f}" y2="{drawdown_top + drawdown_h}" stroke="#eeeeea" stroke-width="1"/>')
            lines.append(f'<text class="tick" x="{x_pos:.2f}" y="{height - 45}" text-anchor="middle">{tick.year}</text>')

    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + equity_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{top + equity_h}" x2="{left + plot_w}" y2="{top + equity_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<text class="small" x="{left}" y="{drawdown_top - 16}">Drawdown od poprzedniego szczytu</text>')
    for i in range(6):
        value = dd_floor * i / 5
        y_pos = y_drawdown(value)
        lines.append(f'<line x1="{left}" y1="{y_pos:.2f}" x2="{left + plot_w}" y2="{y_pos:.2f}" stroke="#deded8" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{left - 10}" y="{y_pos + 4:.2f}" text-anchor="end">{value:.0%}</text>')
    lines.append(f'<line x1="{left}" y1="{drawdown_top}" x2="{left}" y2="{drawdown_top + drawdown_h}" stroke="#333" stroke-width="1.2"/>')
    lines.append(f'<line x1="{left}" y1="{drawdown_top}" x2="{left + plot_w}" y2="{drawdown_top}" stroke="#333" stroke-width="1.2"/>')

    for name in [
        "benchmark_100_equity",
        "benchmark_80_20",
        "benchmark_60_40",
        "strategy_aggressive",
        "strategy_medium_aggressive",
        "strategy_recommended_mix",
        "strategy",
    ]:
        lines.append(
            f'<polyline fill="none" stroke="{colors[name]}" stroke-width="{stroke_widths[name]}" opacity="{opacities[name]}" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{path_points(equity[name], y_equity)}"/>'
        )
        lines.append(
            f'<polyline fill="none" stroke="{colors[name]}" stroke-width="{drawdown_widths[name]}" opacity="{opacities[name]}" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{path_points(drawdown[name], y_drawdown)}"/>'
        )

    legend_x = left + 12
    legend_y = top + 18
    for i, name in enumerate(
        [
            "strategy",
            "strategy_recommended_mix",
            "strategy_medium_aggressive",
            "strategy_aggressive",
            "benchmark_100_equity",
            "benchmark_80_20",
            "benchmark_60_40",
        ]
    ):
        y_pos = legend_y + i * 24
        final_value = float(equity[name].iloc[-1])
        lines.append(f'<line x1="{legend_x}" y1="{y_pos}" x2="{legend_x + 28}" y2="{y_pos}" stroke="{colors[name]}" stroke-width="{max(3.0, stroke_widths[name])}" opacity="{opacities[name]}"/>')
        lines.append(f'<text class="small" x="{legend_x + 38}" y="{y_pos + 5}">{labels[name]}: ${final_value:,.0f}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    out = ["| Portfolio | CAGR | Volatility | Sharpe_0rf | MaxDrawdown | FinalWealth |"]
    out.append("|---|---:|---:|---:|---:|---:|")
    for name, row in df.iterrows():
        out.append(
            f"| {name} | {row['CAGR']:.4f} | {row['Volatility']:.4f} | "
            f"{row['Sharpe_0rf']:.4f} | {row['MaxDrawdown']:.4f} | {row['FinalWealth']:.4f} |"
        )
    return "\n".join(out)


def main() -> None:
    ensure_dirs()
    panel = build_panel()
    result = run_backtest(panel)
    write_reports(result)
    print((REPORTS / "summary.md").resolve())
    print(result.metrics.unstack(1).to_string(float_format=lambda x: f"{x:,.4f}"))


if __name__ == "__main__":
    main()
