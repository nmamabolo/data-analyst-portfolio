"""The trader's RSI rule on every market with free 15-minute data.

Rule (the trader's MT5 setup): M15, RSI(14) on close; SELL when RSI reaches 80, BUY when it
reaches 20, hold until the opposite signal (then flip), with a 3 x ATR(14) safety stop. Seven
fixed variations from gold_rsi run alongside for context.

Markets and data (15-minute bars):
  ejtraderLabs/historical-data (Apache-2.0, Nov 2012 - Mar 2022): AUDJPY AUDUSD EURCHF EURGBP
      EURJPY EURUSD GBPJPY GBPUSD USDCAD USDCHF USDJPY XAUUSD
  This project's own 1-minute sets, rebuilt into M15: EURUSD 2019-2025 (HistData), XAUUSD
      2020-Oct 2026 (gold_rsi), BTCUSD 2019-Oct 2026 (Bitstamp)
  FutureSharks/financial-data (GPL-3.0; Oanda 1-minute bars, Jan 2015 - May 2020): 8 stock indices,
      6 commodities and 4 government bonds, rebuilt into M15
  V75: Deriv's Volatility 75 Index rebuilt from its random-number recipe (v75_sim), 4 years

Each market's history is split into two halves; a result counts only if it holds in both.
Costs: typical retail spread per round trip (table below) plus yearly financing on the
position's value for the time it is held.

  python -m markets.lab
"""
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from gold_rsi.lab import _simulate, signals

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CACHE = HERE / "data_cache"
EJ_REPO = "https://github.com/ejtraderLabs/historical-data"
EJ_COMMIT = "fbd29b3cd85c0eea4f6e8b81c053f98fb3de22fd"
OANDA_REPO = "https://github.com/FutureSharks/financial-data"
OANDA_COMMIT = "7ba1d404aa8b0e1c0f71321acebadcbfb9bcca8d"
OANDA_YEARS = range(2015, 2021)


def _sparse_fetch(dest: Path, repo: str, commit: str, patterns: list[str]) -> Path:
    """Shallow, blob-filtered checkout of only the files we need, at a pinned commit."""
    if dest.exists():
        return dest
    dest.mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", "-C", str(dest), *a], check=True, capture_output=True)
    run("init", "-q")
    run("remote", "add", "origin", repo)
    run("sparse-checkout", "set", "--no-cone", *patterns)
    run("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit)
    run("checkout", "-q", "FETCH_HEAD")
    return dest


def ej_root() -> Path:
    """ejtraderLabs M15 files (~180 MB)."""
    return _sparse_fetch(CACHE / "ejtrader", EJ_REPO, EJ_COMMIT, ["/*/*m15.csv"])


def oanda_root() -> Path:
    """FutureSharks Oanda 1-minute files for the 18 non-FX markets, 2015-2020 (~1.2 GB)."""
    names = sorted({v[0].split(":")[1] for v in MARKETS.values() if v[0].startswith("oanda:")})
    patterns = [f"/pyfinancialdata/data/currencies/oanda/{n}/{y}/*.csv" for n in names for y in OANDA_YEARS]
    return _sparse_fetch(CACHE / "oanda", OANDA_REPO, OANDA_COMMIT, patterns) / "pyfinancialdata/data/currencies/oanda"

# name: (source, spread per round trip in price units, pip size used to express it, yearly financing)
MARKETS = {
    "EURUSD": ("ej", 1.0, 1e-4, 0.01), "GBPUSD": ("ej", 1.5, 1e-4, 0.01), "AUDUSD": ("ej", 1.2, 1e-4, 0.01),
    "USDCAD": ("ej", 1.8, 1e-4, 0.01), "USDCHF": ("ej", 1.6, 1e-4, 0.01), "USDJPY": ("ej", 1.0, 1e-2, 0.01),
    "EURGBP": ("ej", 1.5, 1e-4, 0.01), "EURCHF": ("ej", 2.0, 1e-4, 0.01), "EURJPY": ("ej", 2.0, 1e-2, 0.01),
    "GBPJPY": ("ej", 3.0, 1e-2, 0.01), "AUDJPY": ("ej", 2.0, 1e-2, 0.01), "XAUUSD": ("ej", 0.40, 1.0, 0.04),
    "EURUSD (2019-25)": ("histdata", 1.0, 1e-4, 0.01), "XAUUSD (2020-26)": ("gold", 0.40, 1.0, 0.04),
    "BTCUSD (2019-26)": ("btc", None, None, 0.05), "V75 (simulated)": ("v75", None, None, 0.0),
    # Oanda CFDs, Jan 2015 - May 2020; spread per round trip in index points / price units (approximate retail)
    "S&P 500": ("oanda:SPX500_USD", 0.5, 1.0, 0.04), "Nasdaq 100": ("oanda:NAS100_USD", 1.5, 1.0, 0.04),
    "Russell 2000": ("oanda:US2000_USD", 0.3, 1.0, 0.04), "Nikkei 225": ("oanda:JP225_USD", 10.0, 1.0, 0.04),
    "FTSE 100": ("oanda:UK100_GBP", 1.5, 1.0, 0.04), "CAC 40": ("oanda:FR40_EUR", 1.5, 1.0, 0.04),
    "AEX 25": ("oanda:NL25_EUR", 0.2, 1.0, 0.04), "ASX 200": ("oanda:AU200_AUD", 2.0, 1.0, 0.04),
    "WTI oil": ("oanda:WTICO_USD", 0.04, 1.0, 0.04), "Natural gas": ("oanda:NATGAS_USD", 0.006, 1.0, 0.04),
    "Corn": ("oanda:CORN_USD", 0.01, 1.0, 0.04), "Wheat": ("oanda:WHEAT_USD", 0.015, 1.0, 0.04),
    "Soybeans": ("oanda:SOYBN_USD", 0.02, 1.0, 0.04), "Sugar": ("oanda:SUGAR_USD", 0.0005, 1.0, 0.04),
    "US 10y T-note": ("oanda:USB10Y_USD", 0.05, 1.0, 0.04), "US 2y T-note": ("oanda:USB02Y_USD", 0.03, 1.0, 0.04),
    "German Bund": ("oanda:DE10YB_EUR", 0.05, 1.0, 0.04), "UK Gilt": ("oanda:UK10YB_GBP", 0.06, 1.0, 0.04),
}
PCT_COSTS = {"BTCUSD (2019-26)": 0.0030, "V75 (simulated)": 0.00057}     # round trip as a fraction of price
VARIANTS = [("touch", "reverse"), ("touch", "rsi_50"), ("touch", "atr_2_2"), ("touch", "atr_2_4"),
            ("confirm", "reverse"), ("confirm", "rsi_50"), ("confirm", "atr_2_2"), ("confirm", "atr_2_4")]
TRADERS = ("touch", "reverse")


def m15(m1: pd.DataFrame) -> pd.DataFrame:
    b = m1.resample("15min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b["segment"] = (b.index.to_series().diff() > pd.Timedelta(days=4)).cumsum().to_numpy()
    return b


def load(name: str) -> pd.DataFrame:
    src = MARKETS[name][0]
    if src == "ej":
        sym = name.split()[0]
        df = pd.read_csv(ej_root() / sym / f"{sym}m15.csv", parse_dates=["Date"], index_col="Date")
        df.index = df.index.tz_localize("UTC")          # broker clock; irrelevant for M15 RSI signals
        # The files store prices as integers: 5-digit pairs x 100,000, yen pairs x 1,000, gold x 100.
        scale = 100.0 if sym == "XAUUSD" else 1_000.0 if sym.endswith("JPY") else 100_000.0
        b = df[["open", "high", "low", "close"]].astype(float) / scale
        b = b[~b.index.duplicated()].sort_index()
        b["segment"] = (b.index.to_series().diff() > pd.Timedelta(days=4)).cumsum().to_numpy()
        return b
    if src.startswith("oanda:"):
        files = sorted(f for y in OANDA_YEARS for f in (oanda_root() / src.split(":")[1] / str(y)).glob("*.csv"))
        df = pd.concat([pd.read_csv(f, usecols=["time", "open", "high", "low", "close"]) for f in files])
        df.index = pd.to_datetime(df.pop("time")).dt.tz_localize("UTC")
        df = df[~df.index.duplicated()].sort_index().astype(float)
        return m15(df)
    if src == "histdata":
        from scalping.data_m1 import load as eur
        return m15(eur()[["open", "high", "low", "close"]])
    if src == "gold":
        from gold_rsi.lab import bars, load_m1
        return bars(load_m1(), "15min")
    if src == "btc":
        from rsi_ichimoku.lab import btcusd_m1
        return m15(btcusd_m1())
    from v75_sim.lab import simulate_year
    rng = np.random.default_rng(2026)
    years = [simulate_year(rng) for _ in range(4)]
    for i in range(1, 4):                                            # chain the years end to end
        scale = years[i - 1].close.iloc[-1] / years[i].open.iloc[0]
        years[i][["open", "high", "low", "close"]] *= scale
        years[i].index = years[i].index + pd.DateOffset(years=i)
    return pd.concat(years).assign(segment=0)


def cost_fraction(name: str, price: float) -> float:
    if name in PCT_COSTS:
        return PCT_COSTS[name]
    _, spread, pip, _ = MARKETS[name]
    return spread * pip / price if pip != 1.0 else spread / price


def trades(b: pd.DataFrame, name: str, entry: str, exit_: str) -> pd.DataFrame:
    el, es, xl, xs, end, stop, target = signals(b, entry, exit_, "none")
    o, h, l, c = (b[x].to_numpy(np.float64) for x in ("open", "high", "low", "close"))
    ent, ext, side, pnl, _ = _simulate(o, h, l, c, el, es, xl, xs, end, stop, target)
    t = pd.DataFrame({"entry_time": b.index[ent], "exit_time": b.index[ext], "side": side,
                      "gross": pnl / o[ent]})
    held_years = (t.exit_time - t.entry_time).dt.total_seconds() / (365 * 86_400)
    t["net"] = t.gross - cost_fraction(name, float(np.median(o))) - MARKETS[name][3] * held_years
    return t


def score(t: pd.DataFrame, years: float) -> dict:
    if len(t) < 5:
        return dict(trades=len(t))
    wins, losses = t.net[t.net > 0].sum(), -t.net[t.net <= 0].sum()
    return dict(trades=len(t), win_rate=(t.net > 0).mean(), gross_bp=t.gross.mean() * 1e4, net_bp=t.net.mean() * 1e4,
                profit_factor=wins / losses if losses > 0 else np.inf,
                net_pct_per_year=t.net.sum() / years * 100)


def main():
    RESULTS.mkdir(exist_ok=True)
    rows = []
    for name in MARKETS:
        b = load(name)
        mid = b.index[0] + (b.index[-1] - b.index[0]) / 2
        halves = {"first half": (b.index[0], mid), "second half": (mid, b.index[-1])}
        print(f"{name}: {len(b):,} M15 bars, {b.index[0].date()} to {b.index[-1].date()}")
        for entry, exit_ in VARIANTS:
            t = trades(b, name, entry, exit_)
            for half, (a, z) in halves.items():
                part = t[(t.entry_time >= a) & (t.entry_time < z)]
                years = (z - a).days / 365.25
                rows.append(dict(market=name, entry=entry, exit=exit_, half=half,
                                 start=a.date(), end=z.date(), **score(part, years)))
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "all_markets.csv", index=False, float_format="%.4f")
    traders_rule_table(table).to_csv(RESULTS / "traders_rule_by_market.csv", index=False, float_format="%.4f")
    return table


def group_of(name: str) -> str:
    if "V75" in name:
        return "Random (V75)"
    if "XAU" in name:
        return "Metal"
    if "BTC" in name:
        return "Crypto"
    if any(k in name for k in ("T-note", "Bund", "Gilt")):
        return "Bond"
    if name in ("WTI oil", "Natural gas", "Corn", "Wheat", "Soybeans", "Sugar"):
        return "Commodity"
    return "Currency" if MARKETS[name][0] in ("ej", "histdata") else "Stock index"


def traders_rule_table(table: pd.DataFrame) -> pd.DataFrame:
    """The trader's rule per market: edge, t-statistic, both halves, and where the profit came from."""
    rows = []
    for name in MARKETS:
        b = load(name)
        t = trades(b, name, *TRADERS)
        halves = table[(table.market == name) & (table.entry == TRADERS[0]) & (table.exit == TRADERS[1])].set_index("half")
        years = (b.index[-1] - b.index[0]).days / 365.25
        rows.append(dict(market=name, group=group_of(name), trades=len(t), gross_bp=t.gross.mean() * 1e4,
                         net_bp=t.net.mean() * 1e4, t_stat=t.net.mean() / (t.net.std() / np.sqrt(len(t))),
                         half1_net_bp=halves.loc["first half", "net_bp"], half2_net_bp=halves.loc["second half", "net_bp"],
                         net_pct_per_year=t.net.sum() / years * 100, win_rate=(t.net > 0).mean(),
                         sells_total_pct=t[t.side < 0].net.sum() * 100, buys_total_pct=t[t.side > 0].net.sum() * 100,
                         market_move_pct=(b.close.iloc[-1] / b.close.iloc[0] - 1) * 100))
    return pd.DataFrame(rows).sort_values("t_stat", ascending=False)


if __name__ == "__main__":
    main()
