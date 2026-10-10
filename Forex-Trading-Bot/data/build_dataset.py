"""Rebuild data/fx_daily.csv from the Federal Reserve H.10 daily exchange rates.

Source: https://github.com/datasets/exchange-rates (Public Domain, PDDL),
which republishes the Fed H.10 noon buying rates in New York.

Every Fed series is quoted as "foreign currency per 1 USD". Pairs where the
market quotes USD as the quote currency (EUR/USD, GBP/USD, AUD/USD, NZD/USD)
are inverted so every column matches the convention used by brokers.

Usage:  python data/build_dataset.py
"""
from pathlib import Path

import pandas as pd

SOURCE_URL = "https://raw.githubusercontent.com/datasets/exchange-rates/main/data/daily.csv"
START = "2005-01-01"

# market pair -> (Fed country name, invert?)
PAIRS = {
    "EURUSD": ("Euro", True),
    "GBPUSD": ("United Kingdom", True),
    "AUDUSD": ("Australia", True),
    "NZDUSD": ("New Zealand", True),
    "USDJPY": ("Japan", False),
    "USDCHF": ("Switzerland", False),
    "USDCAD": ("Canada", False),
    "USDZAR": ("South Africa", False),
}


def build(source: str = SOURCE_URL) -> pd.DataFrame:
    raw = pd.read_csv(source, parse_dates=["Date"])
    wide = raw.pivot_table(index="Date", columns="Country", values="Exchange rate")
    out = pd.DataFrame(index=wide.index)
    for pair, (country, invert) in PAIRS.items():
        series = wide[country]
        out[pair] = (1.0 / series) if invert else series
    # Fed holidays appear as blank rows; drop days where no pair traded.
    out = out.loc[START:].dropna(how="all")
    return out.round(5)


if __name__ == "__main__":
    target = Path(__file__).with_name("fx_daily.csv")
    df = build()
    df.to_csv(target, index_label="Date")
    print(f"Wrote {len(df):,} rows x {len(df.columns)} pairs to {target} "
          f"({df.index.min().date()} to {df.index.max().date()})")
