"""Build the multi-asset universe for the strategy factory.

Every source is a public GitHub file pinned to an exact commit, downloaded on
first use into data_cache/ (git-ignored). Nothing here is synthetic.

Daily tradables (close prices):
  8 USD FX pairs   Federal Reserve H.10 noon rates      datasets/exchange-rates (PDDL)
  BTCUSD           Bitstamp, resampled from 1-minute    ff137/bitstamp-btcusd-minute-data
                   "Zielak (mczielinski), Bitcoin Historical Data, Kaggle" (CC BY-SA 4.0)
                   + "Bitstamp BTC/USD minute data, github.com/ff137/bitstamp-btcusd-minute-data" (CC BY 4.0)
  WTI, BRENT       EIA spot prices                      datasets/oil-prices (PDDL)
Daily signal only (not tradable): VIX close              datasets/finance-vix
Monthly tradables: S&P 500 total return (Shiller data, datasets/s-and-p-500)
and gold (datasets/gold-prices). These are monthly AVERAGES, so the monthly
backtest skips a month between signal and trade.

Left out on purpose: Henry Hub natural gas (a physical spot price with
weather spikes to $30 that futures never saw; not tradable) and Shiller's
10-year yield (it stops in Sep 2023, before the final test period ends).
"""
import gzip
import io
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent / "data_cache"
GH = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"
SOURCES = {
    "fx": ("datasets/exchange-rates", "537db850aaa26d4be1adf3a076c6ae60c9f80df8", "data/daily.csv"),
    "wti": ("datasets/oil-prices", "b1d944f94308b9ad0a44a37fc424492b77c362e0", "data/wti-daily.csv"),
    "brent": ("datasets/oil-prices", "b1d944f94308b9ad0a44a37fc424492b77c362e0", "data/brent-daily.csv"),
    "vix": ("datasets/finance-vix", "3dbea23c70cc2afbeeec8ac232c9ec72ac26ac21", "data/vix-daily.csv"),
    "shiller": ("datasets/s-and-p-500", "07b81e6af68239acd65b901a11844d6d95db6ead", "data/data.csv"),
    "gold": ("datasets/gold-prices", "f6e97610178379ef8db280702fcaa3ec0875c5c2", "data/monthly.csv"),
    "btc_hist": ("ff137/bitstamp-btcusd-minute-data", "5038f3156ef0782374a9a0a3b39b8f11de88216f",
                 "data/historical/btcusd_bitstamp_1min_2012-2025.csv.gz"),
    "btc_new": ("ff137/bitstamp-btcusd-minute-data", "5038f3156ef0782374a9a0a3b39b8f11de88216f",
                "data/updates/btcusd_bitstamp_1min_latest.csv"),
}
FX_PAIRS = {"EURUSD": ("Euro", True), "GBPUSD": ("United Kingdom", True), "AUDUSD": ("Australia", True),
            "NZDUSD": ("New Zealand", True), "USDJPY": ("Japan", False), "USDCHF": ("Switzerland", False),
            "USDCAD": ("Canada", False), "USDZAR": ("South Africa", False)}

# One-way trading cost per unit of position change, and yearly cost of holding one unit
# (spread/commission; financing, futures roll or funding). Deliberately on the cautious side.
COSTS = {**{p: (0.00010, 0.01) for p in FX_PAIRS}, "USDZAR": (0.00050, 0.02),
         "BTCUSD": (0.00150, 0.05), "WTI": (0.00030, 0.04), "BRENT": (0.00030, 0.04)}
MONTHLY_COSTS = {"SP500": (0.0005, 0.001), "GOLD": (0.0010, 0.004)}
DAILY_START = "2000-01-01"


def _download(key: str) -> Path:
    repo, sha, path = SOURCES[key]
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{key}_{Path(path).name}"
    if not target.exists():
        print(f"Downloading {repo}/{path} ...")
        urllib.request.urlretrieve(GH.format(repo=repo, sha=sha, path=path), target)
    return target


def _btc_daily() -> pd.Series:
    cached = CACHE / "btc_daily.csv"
    if cached.exists():
        return pd.read_csv(cached, index_col=0, parse_dates=True).iloc[:, 0]
    closes = []
    for key in ("btc_hist", "btc_new"):
        path = _download(key)
        reader = pd.read_csv(path, usecols=["timestamp", "close"], chunksize=2_000_000)
        for chunk in reader:
            t = pd.to_datetime(chunk["timestamp"], unit="s")
            closes.append(chunk.set_index(t)["close"].resample("D").last().dropna())
    s = pd.concat(closes).groupby(level=0).last().rename("BTCUSD")
    s = s.loc["2012-01-01":]
    s.to_csv(cached)
    return s


def daily_prices() -> pd.DataFrame:
    """Close prices of the daily tradables, one column per market (business-day index)."""
    raw = pd.read_csv(_download("fx"), parse_dates=["Date"])
    wide = raw.pivot_table(index="Date", columns="Country", values="Exchange rate")
    cols = {pair: (1 / wide[c] if inv else wide[c]) for pair, (c, inv) in FX_PAIRS.items()}
    for key, name in (("wti", "WTI"), ("brent", "BRENT")):
        s = pd.read_csv(_download(key), parse_dates=["Date"], index_col="Date")["Price"]
        cols[name] = s[s > 0]   # WTI printed negative in April 2020; spot can't be log-returned there
    cols["BTCUSD"] = _btc_daily()
    df = pd.DataFrame(cols).loc[DAILY_START:]
    df = df[df.index.dayofweek < 5]           # BTC trades weekends; align everything to weekdays
    return df


def vix() -> pd.Series:
    v = pd.read_csv(_download("vix"), parse_dates=["DATE"], index_col="DATE")["CLOSE"]
    return v.rename("VIX")


def monthly_returns() -> pd.DataFrame:
    """Monthly total returns: S&P 500 (price + dividends) and gold.

    Shiller dividends stop in mid-2023; the last dividend is carried forward
    (about 1.3% a year, a small part of the return)."""
    sh = pd.read_csv(_download("shiller"), parse_dates=["Date"], index_col="Date")
    sh = sh.replace(0.0, np.nan)
    price, div = sh["SP500"], sh["Dividend"].ffill()
    sp = (price + div / 12) / price.shift(1) - 1
    gold = pd.read_csv(_download("gold"))
    gold.index = pd.to_datetime(gold["Date"] + "-01")
    gold = gold["Price"].pct_change()
    out = pd.DataFrame({"SP500": sp, "GOLD": gold}).loc["1971-09-01":]
    return out.dropna(how="all")
