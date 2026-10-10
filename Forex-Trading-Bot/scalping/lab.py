"""Scalping lab: tune every strategy on 2019-2022, then test once on 2023-2025.

  python -m scalping.lab            # writes results to scalping/results/
"""
from itertools import product
from pathlib import Path

import pandas as pd

from .data_m1 import load
from .engine import score, simulate
from .strategies import STRATEGIES

RESULTS = Path(__file__).resolve().parent / "results"
IN_SAMPLE = (None, "2022-12-31")
OUT_OF_SAMPLE = ("2023-01-01", None)
COSTS = {"no_cost": 0.0, "ecn_best": 0.6, "typical": 1.0}   # round-trip pips
SELECT_COST = COSTS["typical"]
MIN_TRADES = 300

GRIDS = {
    "Asian Bollinger fade": dict(tf=[1, 5, 15], n=[20, 50], k=[2.0, 2.5, 3.0], stop_pips=[5, 8, 12, 20]),
    "London breakout": dict(buffer_pips=[0, 2, 5], tp_mult=[0.5, 1, 2], min_range=[5, 10, 15], max_range=[30, 50]),
    "RSI(2) trend pullback": dict(tf=[1, 5, 15], lo=[5, 10], sl_atr=[1, 2, 3], tp_atr=[0.5, 1, 2], hold=[12, 48]),
    "1-min impulse momentum": dict(k=[2, 3, 4, 6], sl_atr=[1, 2, 3], tp_atr=[1, 2, 4], hold=[5, 15, 60]),
    "1-min impulse fade": dict(k=[2, 3, 4, 6], sl_atr=[1, 2, 3], tp_atr=[1, 2, 4], hold=[5, 15, 60]),
    "NY opening-range breakout": dict(range_end=["08:15", "08:30", "09:00", "09:30"],
                                      tp_mult=[0.5, 1, 1.5, 2, 3], max_range=[15, 25, 40]),
    "EMA trend pullback": dict(tf=[1, 5, 15], fast=[10, 20], slow=[50, 100], tp_r=[1, 1.5, 2, 3], swing=[5, 10]),
    "London 4pm fix reversal": dict(lookback=["15:00", "15:30", "15:45"], min_move=[3, 5, 10, 15],
                                    stop_mult=[0.5, 1, 2], tp_mult=[0.5, 1], exit_at=["16:30", "17:00", "18:00"]),
}


def run(builder, bars, params):
    s = builder(bars, **params)
    return simulate(s.bars, s.signal, s.stop, s.target, s.flat, s.max_hold)


def tune(name, bars_is):
    grid = GRIDS[name]
    rows = []
    for values in product(*grid.values()):
        params = dict(zip(grid, values))
        trades = run(STRATEGIES[name], bars_is, params)
        rows.append({"strategy": name, "params": params, **score(trades, SELECT_COST)})
    table = pd.DataFrame(rows)
    eligible = table[table.trades >= MIN_TRADES]
    return table, eligible.sort_values("net_pips_per_trade", ascending=False).iloc[0]


def main():
    m1 = load()
    bars_is, bars_oos = m1.loc[:IN_SAMPLE[1]], m1.loc[OUT_OF_SAMPLE[0]:]
    RESULTS.mkdir(exist_ok=True)
    all_grids, summary, trade_logs = [], [], {}
    for name in STRATEGIES:
        table, best = tune(name, bars_is)
        all_grids.append(table)
        params = best["params"]
        trades = {"in_sample": run(STRATEGIES[name], bars_is, params),
                  "out_of_sample": run(STRATEGIES[name], bars_oos, params)}
        trade_logs[name] = trades["out_of_sample"]
        for period, t in trades.items():
            for cost_name, cost in COSTS.items():
                summary.append({"strategy": name, "params": params, "period": period,
                                "cost": cost_name, "combos_tested": len(table), **score(t, cost)})
        print(f"{name:28s} best IS net {best.net_pips_per_trade:+.2f} pips/trade  {params}")
    summary = pd.DataFrame(summary)
    summary.to_csv(RESULTS / "summary.csv", index=False, float_format="%.4f")
    pd.concat(all_grids).to_csv(RESULTS / "grid_in_sample.csv", index=False, float_format="%.4f")
    for name, t in trade_logs.items():
        t.to_csv(RESULTS / f"oos_trades_{name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.csv.gz",
                 index=False)
    return summary


if __name__ == "__main__":
    main()
