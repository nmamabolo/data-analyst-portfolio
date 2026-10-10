"""Generate thousands of strategies, filter them like a quant desk, test the survivors once.

Protocol (fixed before any results were seen):
  1. DISCOVER   2000-2016   net Sharpe >= 0.5, >= 10 trades, in the market >= 5% of days
  2. CONFIRM    2017-2020   net Sharpe >= 0.5 again, >= 10 trades
  3. FINAL TEST 2021-2026   reported once, never used to choose anything
  Luck control: the same strategies run on shuffled returns (patterns destroyed,
  volatility and fat tails kept). Survivors there are pure luck, so the count
  tells us how many real-data survivors to expect by chance alone.

  python -m factory.run
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .data import COSTS, daily_prices, vix
from .generator import describe, positions, random_specs, xs_positions

RESULTS = Path(__file__).resolve().parent / "results"
SPLITS = {"discover": ("2000-01-01", "2016-12-31"), "confirm": ("2017-01-01", "2020-12-31"),
          "final": ("2021-01-01", None)}
RULES = dict(min_sharpe=0.5, min_trades=10, min_exposure=0.05)
N_SINGLE, N_XS = 3000, 96
DAYS = 252


def load():
    prices = daily_prices().ffill(limit=5)
    v = vix().reindex(prices.index).ffill().shift(1)   # yesterday's close: VIX settles after FX fixings
    return prices, v


def strategy_returns(pos: pd.Series, ret: pd.Series, asset: str) -> pd.Series:
    """Daily net return of holding `pos` (decided at each close) in `asset`."""
    trade_cost, hold_cost = COSTS[asset]
    held = pos.shift(1).fillna(0.0)
    turnover = held.diff().abs().fillna(held.abs())
    return held * ret.fillna(0.0) - trade_cost * turnover - hold_cost / DAYS * held.abs()


def basket_returns(weights: pd.DataFrame, rets: pd.DataFrame) -> pd.Series:
    held = weights.shift(1).fillna(0.0)
    turnover = held.diff().abs().fillna(held.abs())
    tc = pd.Series({a: COSTS[a][0] for a in rets}, dtype=float)
    hc = pd.Series({a: COSTS[a][1] for a in rets}, dtype=float)
    return ((held * rets.fillna(0.0)).sum(axis=1) - (turnover * tc).sum(axis=1)
            - (held.abs() * hc).sum(axis=1) / DAYS)


def split_stats(r: pd.Series, pos_change: pd.Series, exposure: pd.Series) -> dict:
    out = {}
    for name, (a, b) in SPLITS.items():
        x = r.loc[a:b]
        live = exposure.loc[a:b]
        first = live[live.notna()].index.min()
        x = x.loc[first:] if first is not None else x.iloc[:0]
        sd = x.std()
        out[f"{name}_sharpe"] = x.mean() / sd * np.sqrt(DAYS) if sd > 0 else np.nan
        out[f"{name}_ann_return"] = x.mean() * DAYS
        out[f"{name}_trades"] = int((pos_change.loc[a:b] > 0).sum())
        out[f"{name}_exposure"] = float((live.loc[first:] > 0).mean()) if first is not None else 0.0
    return out


def evaluate_all(prices: pd.DataFrame, v: pd.Series, specs: list[dict]) -> pd.DataFrame:
    rets = prices.pct_change()
    rows = []
    for sid, spec in enumerate(specs):
        if spec["family"].startswith("xs_"):
            w = xs_positions(spec, prices)
            r = basket_returns(w, rets)
            change = w.diff().abs().sum(axis=1)
            exposure = w.abs().sum(axis=1).where(prices.notna().sum(axis=1) > 2)
            rows.append({"id": sid, "asset": "BASKET", "spec": describe(spec),
                         **split_stats(r, change, exposure)})
            continue
        for asset in prices:
            close = prices[asset]
            pos = positions(spec, close, v)
            r = strategy_returns(pos, rets[asset], asset)
            exposure = pos.abs().where(close.notna())
            rows.append({"id": sid, "asset": asset, "spec": describe(spec),
                         **split_stats(r, pos.diff().abs(), exposure)})
    return pd.DataFrame(rows)


def passes(table: pd.DataFrame) -> pd.DataFrame:
    t = table
    ok = ((t.discover_sharpe >= RULES["min_sharpe"]) & (t.discover_trades >= RULES["min_trades"])
          & (t.discover_exposure >= RULES["min_exposure"])
          & (t.confirm_sharpe >= RULES["min_sharpe"]) & (t.confirm_trades >= RULES["min_trades"]))
    return t[ok]


def shuffled_prices(prices: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """Same returns, random order within each split: no real pattern can survive."""
    rng = np.random.default_rng(seed)
    rets = prices.pct_change()
    out = rets.copy()
    for a, b in SPLITS.values():
        block = out.loc[a:b]
        for col in out:
            vals = block[col].to_numpy().copy()
            mask = ~np.isnan(vals)
            vals[mask] = rng.permutation(vals[mask])
            out.loc[block.index, col] = vals
    rebuilt = (1 + out.fillna(0.0)).cumprod() * prices.bfill().iloc[0]
    return rebuilt.where(prices.notna())


def buy_and_hold(prices: pd.DataFrame) -> pd.DataFrame:
    rets = prices.pct_change()
    rows = {}
    for asset in prices:
        pos = pd.Series(1.0, prices.index).where(prices[asset].notna(), 0.0)
        r = strategy_returns(pos, rets[asset], asset)
        rows[asset] = split_stats(r, pos.diff().abs(), pos.where(prices[asset].notna()))
    return pd.DataFrame(rows).T


def main():
    RESULTS.mkdir(exist_ok=True)
    prices, v = load()
    specs = random_specs(N_SINGLE, N_XS)
    n_tests = N_SINGLE * prices.shape[1] + N_XS
    print(f"{len(specs):,} strategy designs x markets = {n_tests:,} strategies to test")

    real = evaluate_all(prices, v, specs)
    real.to_csv(RESULTS / "all_strategies.csv.gz", index=False, float_format="%.4f")
    survivors = passes(real)
    survivors.to_csv(RESULTS / "survivors.csv", index=False, float_format="%.4f")

    null = evaluate_all(shuffled_prices(prices), v, specs)
    null_survivors = passes(null)
    null.to_csv(RESULTS / "luck_control.csv.gz", index=False, float_format="%.4f")

    buy_and_hold(prices).to_csv(RESULTS / "buy_and_hold.csv", float_format="%.4f")
    print(f"Passed discover+confirm on REAL data:     {len(survivors):,}")
    print(f"Passed discover+confirm on SHUFFLED data: {len(null_survivors):,}  (expected by luck)")
    print(f"Final-test Sharpe of real survivors: median {survivors.final_sharpe.median():.2f}, "
          f"{(survivors.final_sharpe > 0).mean():.0%} positive")
    return real, survivors, null_survivors


if __name__ == "__main__":
    main()
