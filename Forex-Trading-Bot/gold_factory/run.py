"""Gold-only strategy factory: create thousands of rules for XAU/USD and keep what survives.

Data: 1-minute spot gold, Jan 2020 - Oct 2026 (see gold_rsi.lab), rebuilt into M15, H1,
H4 and D1 bars. The data is split at its four 2025 holes: every rule restarts after a
hole and nothing is held across one.

Strategies:
  * the factory's building blocks (trend, momentum, breakouts, mean reversion, volatility
    shocks; calendar rules on D1 only), with random parameters, filters and directions
  * a gold-specific time-of-day family on M15/H1: hold long or short from UTC hour h for
    k hours every weekday

Protocol (fixed before any results were seen):
  DISCOVER 2020-2022, CONFIRM 2023-2024: net Sharpe >= 0.5 in both, >= 10 trades each,
  in the market >= 5% of the time. FINAL TEST 2025 - Oct 2026: reported once.
  Luck control: the same rules on shuffled returns (order destroyed, drift kept).
  Costs: $0.40 per ounce per round trip, plus 4% a year financing on the position's value.

  python -m gold_factory.run
"""
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from factory.generator import describe, positions, random_specs
from gold_rsi.lab import COSTS, FINANCING, bars, load_m1

RESULTS = Path(__file__).resolve().parent / "results"
SPLITS = {"discover": ("2020-01-01", "2022-12-31"), "confirm": ("2023-01-01", "2024-12-31"),
          "final": ("2025-01-01", None)}
RULES = dict(min_sharpe=0.5, min_trades=10, min_exposure=0.05)
TIMEFRAMES = {"M15": "15min", "H1": "1h", "H4": "4h", "D1": "24h"}
N_RANDOM = 1500
ROUND_TRIP = COSTS["typical_cost"]          # $ per ounce
NO_VIX = pd.Series(dtype=float)


def gold_bars(tf: str) -> pd.DataFrame:
    b = bars(load_m1(), TIMEFRAMES[tf]) if tf != "D1" else _daily()
    return b


def _daily() -> pd.DataFrame:
    """Daily sessions from 22:00 UTC, labelled with the session's own date."""
    m1 = load_m1()
    d = m1.resample("24h", offset="22h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    d.index = (d.index + pd.Timedelta(hours=2)).normalize()
    d = d[d.index.dayofweek < 5]
    d["segment"] = (d.index.to_series().diff() > pd.Timedelta(days=4)).cumsum().to_numpy()
    return d


def specs_for(tf: str) -> list[dict]:
    keep = []
    for s in random_specs(N_RANDOM, 0):
        if s["family"].startswith("vix") or s["filter"].startswith("vix"):
            continue
        if tf != "D1" and s["family"] in ("weekday", "turn_of_month"):
            continue
        keep.append(s)
    if tf in ("M15", "H1"):
        for h, k, d in product(range(24), (1, 2, 4, 8), ("long_only", "short_only")):
            keep.append(dict(family="hour_of_day", params=dict(start_utc=h, hours=k), filter="none",
                             filter_params={}, direction=d, max_hold=0))
    return keep


def hour_positions(spec: dict, close: pd.Series, step: pd.Timedelta) -> pd.Series:
    """Hold during the bar that starts next if it falls in [start, start + hours) UTC on a weekday."""
    nxt = close.index + step
    h0, k = spec["params"]["start_utc"], spec["params"]["hours"]
    inside = ((nxt.hour - h0) % 24) < k
    sign = 1.0 if spec["direction"] == "long_only" else -1.0
    return pd.Series(np.where(inside & (nxt.dayofweek < 5), sign, 0.0), close.index)


def spec_positions(spec: dict, b: pd.DataFrame, step: pd.Timedelta) -> pd.Series:
    """Positions computed separately inside each data segment, flat on each segment's last bar."""
    parts = []
    for _, seg in b.groupby("segment", sort=True):
        close = seg.close
        p = hour_positions(spec, close, step) if spec["family"] == "hour_of_day" else positions(spec, close, NO_VIX)
        p.iloc[-1] = 0.0
        parts.append(p)
    return pd.concat(parts)


def net_returns(pos: pd.Series, b: pd.DataFrame, step: pd.Timedelta) -> pd.Series:
    held = pos.shift(1).fillna(0.0)
    ret = b.close.pct_change()
    ret[b.segment.diff().fillna(0) != 0] = 0.0             # no return across a data hole
    turnover = held.diff().abs().fillna(held.abs())
    trade_cost = (ROUND_TRIP / 2) / b.close.shift(1)       # half the round trip on each change
    hold_cost = FINANCING * (step / pd.Timedelta(days=365))
    return held * ret.fillna(0.0) - turnover * trade_cost.fillna(0.0) - held.abs() * hold_cost


def stats(r: pd.Series, pos: pd.Series) -> dict:
    daily = r.groupby(r.index.normalize()).sum()
    out = {}
    for name, (a, b) in SPLITS.items():
        x = daily.loc[a:b]
        p = pos.loc[a:b]
        sd = x.std()
        out[f"{name}_sharpe"] = x.mean() / sd * np.sqrt(252) if sd > 0 else np.nan
        out[f"{name}_ann_return"] = x.mean() * 252
        out[f"{name}_trades"] = int((p.diff().abs() > 0).sum() // 2)
        out[f"{name}_exposure"] = float((p != 0).mean())
    return out


def evaluate(b: pd.DataFrame, tf: str, specs: list[dict]) -> pd.DataFrame:
    step = pd.Timedelta(TIMEFRAMES[tf]) if tf != "D1" else pd.Timedelta(days=1)
    rows = []
    for sid, spec in enumerate(specs):
        pos = spec_positions(spec, b, step)
        rows.append({"timeframe": tf, "id": sid, "spec": describe(spec), "family": spec["family"],
                     **stats(net_returns(pos, b, step), pos)})
    return pd.DataFrame(rows)


def passes(t: pd.DataFrame) -> pd.DataFrame:
    return t[(t.discover_sharpe >= RULES["min_sharpe"]) & (t.confirm_sharpe >= RULES["min_sharpe"])
             & (t.discover_trades >= RULES["min_trades"]) & (t.confirm_trades >= RULES["min_trades"])
             & (t.discover_exposure >= RULES["min_exposure"])]


def shuffled(b: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """Same bar returns in random order within each split and data segment; drift kept, timing destroyed."""
    rng = np.random.default_rng(seed)
    r = np.log(b.close).diff().fillna(0.0).to_numpy()
    out = r.copy()
    period = np.select([b.index < pd.Timestamp(SPLITS["confirm"][0], tz=b.index.tz),
                        b.index < pd.Timestamp(SPLITS["final"][0], tz=b.index.tz)], [0, 1], 2)
    for key in set(zip(period, b.segment)):
        mask = (period == key[0]) & (b.segment.to_numpy() == key[1])
        out[mask] = rng.permutation(out[mask])
    close = float(b.close.iloc[0]) * np.exp(np.cumsum(out))
    return b.assign(close=close)


def buy_and_hold(b: pd.DataFrame, tf: str) -> dict:
    step = pd.Timedelta(TIMEFRAMES[tf]) if tf != "D1" else pd.Timedelta(days=1)
    pos = pd.Series(1.0, b.index)
    return stats(net_returns(pos, b, step), pos)


def main():
    RESULTS.mkdir(exist_ok=True)
    real, luck, bh = [], [], {}
    for tf in TIMEFRAMES:
        b = gold_bars(tf)
        specs = specs_for(tf)
        print(f"{tf}: {len(b):,} bars, {len(specs):,} strategies")
        real.append(evaluate(b, tf, specs))
        luck.append(evaluate(shuffled(b), tf, specs))
        bh[tf] = buy_and_hold(b, tf)
    real, luck = pd.concat(real, ignore_index=True), pd.concat(luck, ignore_index=True)
    real.to_csv(RESULTS / "all_strategies.csv.gz", index=False, float_format="%.4f")
    luck.to_csv(RESULTS / "luck_control.csv.gz", index=False, float_format="%.4f")
    passes(real).to_csv(RESULTS / "survivors.csv", index=False, float_format="%.4f")
    pd.DataFrame(bh).T.to_csv(RESULTS / "buy_and_hold.csv", float_format="%.4f")
    print(f"Tested {len(real):,} | passed on real data: {len(passes(real)):,} | on shuffled data: {len(passes(luck)):,}")


if __name__ == "__main__":
    main()
