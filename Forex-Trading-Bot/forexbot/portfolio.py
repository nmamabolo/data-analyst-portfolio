"""Run the strategy across several pairs and search its parameters."""
from itertools import product

import pandas as pd

from .backtest import BacktestResult, RiskSettings, run_backtest
from .data import PAIRS, load_fed_daily, pair_spec
from .metrics import summarize
from .strategy import MACrossover

IN_SAMPLE = ("2005-01-01", "2018-12-31")
OUT_OF_SAMPLE = ("2019-01-01", None)


def run_pairs(strategy: MACrossover, pairs=None, risk: RiskSettings = RiskSettings(),
              start=None, end=None) -> dict[str, BacktestResult]:
    pairs = pairs or list(PAIRS)
    return {p: run_backtest(load_fed_daily(p), pair_spec(p), strategy, risk, start, end) for p in pairs}


def portfolio_equity(results: dict[str, BacktestResult]) -> pd.Series:
    """Equal-weight portfolio: one sub-account per pair, summed daily.

    Pairs have slightly different holiday calendars, so each sub-account's
    last value is carried forward on days it has no fixing.
    """
    curves = pd.concat([r.equity for r in results.values()], axis=1).ffill().bfill()
    return curves.sum(axis=1).rename("portfolio")


def all_trades(results: dict[str, BacktestResult]) -> pd.DataFrame:
    frames = [r.trades for r in results.values() if len(r.trades)]
    return pd.concat(frames, ignore_index=True).sort_values("entry_date") if frames else pd.DataFrame()


def summary_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = {p: summarize(r.equity, r.trades) for p, r in results.items()}
    rows["PORTFOLIO"] = summarize(portfolio_equity(results), all_trades(results))
    return pd.DataFrame(rows).T


def grid_search(fast_values, slow_values, exits: dict[str, dict], start, end,
                pairs=None) -> pd.DataFrame:
    """Score each parameter set by the median per-pair Sharpe ratio.

    The median across pairs rewards settings that work broadly instead of
    settings that happen to suit one pair.
    """
    rows = []
    for fast, slow, (exit_name, exit_kwargs) in product(fast_values, slow_values, exits.items()):
        if fast >= slow:
            continue
        strategy = MACrossover(fast=fast, slow=slow, **exit_kwargs)
        table = summary_table(run_pairs(strategy, pairs, start=start, end=end))
        per_pair = table.drop(index="PORTFOLIO")
        rows.append({
            "fast": fast, "slow": slow, "exit": exit_name,
            "median_pair_sharpe": per_pair.sharpe.median(),
            "pairs_profitable": int((per_pair.total_return > 0).sum()),
            "portfolio_sharpe": table.loc["PORTFOLIO", "sharpe"],
            "portfolio_cagr": table.loc["PORTFOLIO", "cagr"],
            "portfolio_max_dd": table.loc["PORTFOLIO", "max_drawdown"],
            "trades": int(table.loc["PORTFOLIO", "trades"]),
        })
    return pd.DataFrame(rows).sort_values("median_pair_sharpe", ascending=False, ignore_index=True)
