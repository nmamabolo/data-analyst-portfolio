"""Load price data into a standard OHLC frame indexed by date."""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FED_DAILY = DATA_DIR / "fx_daily.csv"


@dataclass(frozen=True)
class PairSpec:
    symbol: str
    pip: float          # size of one pip in price units
    spread_pips: float  # assumed round-turn cost, charged half on entry, half on exit

    @property
    def base(self) -> str:
        return self.symbol[:3]

    @property
    def quote(self) -> str:
        return self.symbol[3:]


# Spreads are typical retail ECN levels for daily-bar trading, kept on the cautious side.
PAIRS = {
    "EURUSD": PairSpec("EURUSD", 0.0001, 1.0),
    "GBPUSD": PairSpec("GBPUSD", 0.0001, 1.5),
    "AUDUSD": PairSpec("AUDUSD", 0.0001, 1.2),
    "NZDUSD": PairSpec("NZDUSD", 0.0001, 1.8),
    "USDJPY": PairSpec("USDJPY", 0.01, 1.0),
    "USDCHF": PairSpec("USDCHF", 0.0001, 1.5),
    "USDCAD": PairSpec("USDCAD", 0.0001, 1.5),
    "USDZAR": PairSpec("USDZAR", 0.0001, 150.0),
}


def pair_spec(symbol: str) -> PairSpec:
    symbol = symbol.upper()
    if symbol not in PAIRS:
        raise KeyError(f"Unknown pair {symbol!r}. Known: {', '.join(PAIRS)}")
    return PAIRS[symbol]


def load_fed_daily(symbol: str, path: Path = FED_DAILY) -> pd.DataFrame:
    """Daily fixings from the bundled Fed H.10 file, shaped as OHLC bars.

    The file has one price per day. FX trades around the clock, so each bar
    opens at the previous fixing and its range is the span between the two
    fixings. Real intraday ranges are wider, so stops and targets trigger
    less often here than they would on broker OHLC data.
    """
    wide = pd.read_csv(path, index_col="Date", parse_dates=True)
    close = wide[symbol.upper()].dropna()
    open_ = close.shift(1)
    bars = pd.DataFrame({
        "open": open_,
        "high": pd.concat([open_, close], axis=1).max(axis=1),
        "low": pd.concat([open_, close], axis=1).min(axis=1),
        "close": close,
    })
    return bars.iloc[1:]


def load_ohlc_csv(path: str | Path) -> pd.DataFrame:
    """Load a broker OHLC export, such as MetaTrader 5's 'Export Bars' CSV.

    Accepts tab- or comma-separated files with a date column (optionally a
    separate time column) and open/high/low/close columns in any case,
    with or without MT5's <ANGLE> brackets.
    """
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [c.strip("<>").strip().lower() for c in df.columns]
    if "time" in df.columns and "date" in df.columns:
        stamp = df["date"].astype(str) + " " + df["time"].astype(str)
    else:
        stamp = df[next(c for c in ("date", "datetime", "time", "timestamp") if c in df.columns)]
    df.index = pd.to_datetime(stamp)
    df.index.name = "Date"
    return df[["open", "high", "low", "close"]].astype(float).sort_index()
