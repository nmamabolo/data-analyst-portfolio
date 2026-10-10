"""Can $10k become $1M in a year? Monte Carlo on real out-of-sample trades.

Each simulated year redraws (with replacement) a year's worth of trades from
a strategy's 2023-2025 out-of-sample trade log, sizes every trade as a fixed
fraction of current equity at risk, and enforces a broker leverage cap.

  python -m scalping.million
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .lab import RESULTS

START, GOAL, PRICE = 10_000.0, 1_000_000.0, 1.10   # EUR/USD near its 2023-25 average
YEARS = 10_000
RISKS = [0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.00]
LEVERAGE = [30, 500]   # EU/UK retail cap vs offshore broker


def simulate_years(net_pips, risk_pips, trades_per_year, risk, leverage, seed=7):
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(net_pips), size=(YEARS, trades_per_year))
    pnl_pips, stop_pips = net_pips[draws], risk_pips[draws]
    # Fraction of equity lost per pip: intended risk / stop, but never more than leverage allows.
    max_per_pip = leverage * 0.0001 / PRICE
    per_pip = np.minimum(risk / stop_pips, max_per_pip)
    growth = np.clip(1 + per_pip * pnl_pips, 0, None)   # equity cannot go below zero
    equity = START * np.cumprod(growth, axis=1)
    final = equity[:, -1]
    peak = np.maximum.accumulate(np.concatenate([np.full((YEARS, 1), START), equity], axis=1), axis=1)
    worst_dd = (equity / peak[:, 1:] - 1).min(axis=1)
    return final, worst_dd


def required_sharpe(multiple=GOAL / START):
    """Annual Sharpe needed to compound to `multiple` in one year at the growth-optimal (Kelly) bet.

    Growth per year at the Kelly fraction is S^2 / 2 (log terms), so S = sqrt(2 ln multiple).
    """
    return np.sqrt(2 * np.log(multiple))


def main(cost_pips=0.6):
    rows = []
    for path in sorted(RESULTS.glob("oos_trades_*.csv.gz")):
        trades = pd.read_csv(path, parse_dates=["entry_time"])
        name = path.name.removeprefix("oos_trades_").removesuffix(".csv.gz").replace("_", " ")
        net = trades.gross_pips.to_numpy() - cost_pips
        years = (trades.entry_time.iloc[-1] - trades.entry_time.iloc[0]).days / 365.25
        per_year = int(round(len(trades) / years))
        daily_r = (pd.Series(net / trades.risk_pips.to_numpy(), index=trades.entry_time)
                   .resample("B").sum())
        sharpe = daily_r.mean() / daily_r.std() * np.sqrt(252)
        for lev in LEVERAGE:
            for risk in RISKS:
                final, dd = simulate_years(net, trades.risk_pips.to_numpy(), per_year, risk, lev)
                rows.append({"strategy": name, "annual_sharpe": sharpe, "trades_per_year": per_year,
                             "leverage": lev, "risk_per_trade": risk,
                             "p_reach_1m": (final >= GOAL).mean(),
                             "p_lose_90pct": (final <= 0.1 * START).mean(),
                             "median_final": np.median(final),
                             "p90_final": np.quantile(final, 0.9),
                             "median_worst_dd": np.median(dd)})
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "million_monte_carlo.csv", index=False, float_format="%.5f")
    return table


if __name__ == "__main__":
    t = main()
    print(f"Annual Sharpe needed for 100x in a year at the optimal bet size: {required_sharpe():.2f}\n")
    best = t.sort_values("p_reach_1m", ascending=False).groupby("strategy").head(1)
    print(best.to_string(index=False))
