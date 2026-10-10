"""Turn surviving strategies into one income portfolio, using only pre-2021 data.

Rules (fixed before the final test was looked at):
  1. Rank daily survivors by the weaker of their discover / confirm Sharpe.
  2. Walk down the ranking; keep a strategy only if its daily returns correlate
     < 0.5 with every strategy already kept, with at most 2 per market and 12 in total.
  3. Weight the kept strategies by inverse volatility (2000-2020 estimate).
  4. Monthly sleeve: the monthly survivor with the best weaker-of-two Sharpe.
  5. Combine the two sleeves with equal risk, then scale the whole portfolio to
     a target volatility. Every number used for weights and scaling comes from
     2000-2020; 2021-2026 is only replayed.
"""
import numpy as np
import pandas as pd

from . import monthly
from .generator import positions, random_specs, xs_positions
from .run import N_SINGLE, N_XS, SPLITS, basket_returns, load, strategy_returns

TRAIN_END = SPLITS["confirm"][1]
MAX_CORR, MAX_PER_MARKET, MAX_STRATEGIES = 0.5, 2, 12


def survivor_returns(survivors: pd.DataFrame) -> pd.DataFrame:
    prices, v = load()
    rets = prices.pct_change()
    specs = random_specs(N_SINGLE, N_XS)
    cols = {}
    for row in survivors.itertuples():
        spec = specs[row.id]
        if row.asset == "BASKET":
            r = basket_returns(xs_positions(spec, prices), rets)
        else:
            r = strategy_returns(positions(spec, prices[row.asset], v), rets[row.asset], row.asset)
        cols[f"{row.asset} | {row.spec}"] = r
    return pd.DataFrame(cols)


def select(survivors: pd.DataFrame, returns: pd.DataFrame) -> list[str]:
    ranked = survivors.assign(robust=np.minimum(survivors.discover_sharpe, survivors.confirm_sharpe))
    ranked = ranked.sort_values("robust", ascending=False)
    train = returns.loc[:TRAIN_END]
    chosen, per_market = [], {}
    for row in ranked.itertuples():
        name = f"{row.asset} | {row.spec}"
        if per_market.get(row.asset, 0) >= MAX_PER_MARKET:
            continue
        if chosen and train[chosen].corrwith(train[name]).abs().max() >= MAX_CORR:
            continue
        chosen.append(name)
        per_market[row.asset] = per_market.get(row.asset, 0) + 1
        if len(chosen) == MAX_STRATEGIES:
            break
    return chosen


def daily_sleeve(returns: pd.DataFrame, chosen: list[str]) -> pd.Series:
    vol = returns.loc[:TRAIN_END, chosen].std()
    w = (1 / vol) / (1 / vol).sum()
    return (returns[chosen].fillna(0.0) * w).sum(axis=1).rename("daily_sleeve")


def monthly_sleeve() -> tuple[pd.Series, str]:
    table = monthly.evaluate()
    ok = monthly.passes(table)
    best = ok.assign(robust=np.minimum(ok.discover_sharpe, ok.confirm_sharpe)).sort_values(
        "robust", ascending=False).iloc[0]
    spec = monthly.specs()[int(best.id)]
    return monthly.strategy_returns(spec, monthly.monthly_returns()).rename("monthly_sleeve"), best.spec


def to_monthly(daily: pd.Series) -> pd.Series:
    m = (1 + daily).resample("MS").prod() - 1
    return m


def combine(daily: pd.Series, monthly_r: pd.Series, target_vol: float) -> pd.DataFrame:
    """Monthly returns of each sleeve and of the volatility-targeted portfolio."""
    d = to_monthly(daily)
    m = monthly_r.reindex(d.index)
    sleeves = pd.DataFrame({"daily_sleeve": d, "monthly_sleeve": m}).dropna()
    vol = sleeves.loc[:TRAIN_END].std() * np.sqrt(12)
    w = (1 / vol) / (1 / vol).sum()
    raw = (sleeves * w).sum(axis=1)
    scale = target_vol / (raw.loc[:TRAIN_END].std() * np.sqrt(12))
    sleeves["portfolio"] = raw * scale
    sleeves.attrs.update(weights=w.to_dict(), scale=scale)
    return sleeves
