"""Load HistData EUR/USD 1-minute bars (bid prices) for the scalping lab.

Source: HistData.com Generic ASCII M1 files, as mirrored in the public repo
https://github.com/asiertrades/hisdata-eurusd (one CSV per year, ~20 MB each).
Timestamps are New York standard time with no daylight saving (fixed UTC-5).

The raw CSVs are too large to commit, so `fetch` downloads them on demand
and `load` caches a parquet file next to them.
"""
from pathlib import Path
import urllib.request

import numpy as np
import pandas as pd

# Pinned to the commit the published results were produced from.
RAW_URL = ("https://raw.githubusercontent.com/asiertrades/HISDATA-EURUSD/"
           "7057b9fd5cc1797cb551b70929b93ffdd2945436/DAT_ASCII_EURUSD_M1_{year}.csv")
CACHE = Path(__file__).resolve().parent / "data_cache"
PIP = 0.0001


def fetch(years, cache: Path = CACHE) -> list[Path]:
    cache.mkdir(parents=True, exist_ok=True)
    paths = []
    for year in years:
        path = cache / f"DAT_ASCII_EURUSD_M1_{year}.csv"
        if not path.exists():
            print(f"Downloading EUR/USD M1 {year} ...")
            urllib.request.urlretrieve(RAW_URL.format(year=year), path)
        paths.append(path)
    return paths


def read_histdata(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", header=None,
                     names=["stamp", "open", "high", "low", "close", "volume"],
                     dtype={"stamp": str})
    est = pd.to_datetime(df["stamp"], format="%Y%m%d %H%M%S")
    df.index = (est + pd.Timedelta(hours=5)).dt.tz_localize("UTC")
    return df[["open", "high", "low", "close"]].astype(np.float64)


def load(years=range(2019, 2026), source_dir: Path | None = None) -> pd.DataFrame:
    """1-minute bars indexed by UTC time, with London/New York clock columns."""
    years = list(years)
    cache_file = CACHE / f"eurusd_m1_{years[0]}_{years[-1]}.parquet"
    if cache_file.exists():
        return pd.read_parquet(cache_file)
    if source_dir is None:
        paths = fetch(years)
    else:
        paths = [Path(source_dir) / f"DAT_ASCII_EURUSD_M1_{y}.csv" for y in years]
    bars = pd.concat([read_histdata(p) for p in paths]).sort_index()
    bars = bars[~bars.index.duplicated()]
    london = bars.index.tz_convert("Europe/London")
    new_york = bars.index.tz_convert("America/New_York")
    bars["london_min"] = (london.hour * 60 + london.minute).astype(np.int16)
    bars["ny_min"] = (new_york.hour * 60 + new_york.minute).astype(np.int16)
    # Trading day rolls at 17:00 New York, the FX market's daily close.
    bars["day"] = (new_york - pd.Timedelta(hours=17)).date
    bars["day"] = pd.to_datetime(bars["day"])
    CACHE.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(cache_file)
    return bars
