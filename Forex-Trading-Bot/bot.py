"""Forex trading robot: EMA crossover with ATR trailing stops.

  python bot.py backtest                 # all 8 pairs, full history
  python bot.py backtest --pairs EURUSD --start 2019-01-01
  python bot.py backtest --csv EURUSD_D1.csv --pairs EURUSD   # your own broker OHLC export
  python bot.py optimize                 # tune on 2005-2018, test on 2019-today, write charts
  python bot.py signals --equity 10000   # what the robot holds today and what to do next
"""
import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from forexbot.backtest import RiskSettings, run_backtest
from forexbot.data import PAIRS, load_fed_daily, load_ohlc_csv, pair_spec
from forexbot.metrics import format_summary, summarize
from forexbot.portfolio import (IN_SAMPLE, OUT_OF_SAMPLE, all_trades, grid_search,
                                portfolio_equity, run_pairs, summary_table)
from forexbot.report import equity_chart, heatmap_chart, trades_chart
from forexbot.strategy import MACrossover

RESULTS = Path(__file__).resolve().parent / "results"
SUMMARY_COLUMNS = ["total_return", "cagr", "sharpe", "max_drawdown", "trades",
                   "win_rate", "profit_factor", "expectancy_r"]


def add_strategy_args(parser: argparse.ArgumentParser) -> None:
    d = MACrossover()
    g = parser.add_argument_group("strategy")
    g.add_argument("--fast", type=int, default=d.fast, help=f"fast EMA period (default {d.fast})")
    g.add_argument("--slow", type=int, default=d.slow, help=f"slow EMA period (default {d.slow})")
    g.add_argument("--ma-type", choices=["ema", "sma"], default=d.ma_type)
    g.add_argument("--stop-atr", type=float, default=d.stop_atr, help="stop distance in ATRs")
    g.add_argument("--target-atr", type=float, default=d.target_atr, help="take-profit in ATRs, 0 = none")
    g.add_argument("--no-trailing", dest="trailing", action="store_false", help="keep the stop fixed")
    r = parser.add_argument_group("risk")
    r.add_argument("--equity", type=float, default=10_000, help="starting equity per pair (USD)")
    r.add_argument("--risk", type=float, default=0.01, help="fraction of equity risked per trade")
    r.add_argument("--max-leverage", type=float, default=10.0)


def strategy_from(args) -> MACrossover:
    return MACrossover(args.fast, args.slow, args.ma_type, stop_atr=args.stop_atr,
                       target_atr=args.target_atr, trailing=args.trailing)


def risk_from(args) -> RiskSettings:
    return RiskSettings(args.equity, args.risk, args.max_leverage)


def print_table(table: pd.DataFrame) -> None:
    shown = table[SUMMARY_COLUMNS].apply(lambda row: format_summary(row.to_dict()), axis=1)
    print(shown.to_string())


def cmd_backtest(args) -> None:
    strategy, risk = strategy_from(args), risk_from(args)
    pairs = [p.upper() for p in args.pairs] if args.pairs else list(PAIRS)
    print(f"Strategy: {strategy}\n")
    if args.csv:
        if len(pairs) != 1:
            raise SystemExit("--csv needs exactly one --pairs symbol so costs and P&L convert correctly")
        result = run_backtest(load_ohlc_csv(args.csv), pair_spec(pairs[0]), strategy, risk,
                              args.start, args.end)
        print(format_summary(summarize(result.equity, result.trades)).to_string())
        trades = result.trades
    else:
        results = run_pairs(strategy, pairs, risk, args.start, args.end)
        print_table(summary_table(results))
        trades = all_trades(results)
    RESULTS.mkdir(exist_ok=True)
    trades.to_csv(RESULTS / "backtest_trades.csv", index=False)
    print(f"\nTrade log: {RESULTS / 'backtest_trades.csv'}")


def cmd_optimize(args) -> None:
    exits = {
        "Fixed stop 3 ATR, target 6 ATR": dict(stop_atr=3, target_atr=6, trailing=False),
        "Trailing stop 3 ATR": dict(stop_atr=3, target_atr=0, trailing=True),
        "Trailing stop 5 ATR": dict(stop_atr=5, target_atr=0, trailing=True),
    }
    print(f"Grid search on in-sample data {IN_SAMPLE[0]} to {IN_SAMPLE[1]} ...")
    grid = grid_search([10, 20, 30, 50], [50, 100, 150, 200], exits, *IN_SAMPLE)
    RESULTS.mkdir(exist_ok=True)
    grid.to_csv(RESULTS / "grid_search.csv", index=False, float_format="%.4f")
    print(grid.head(10).to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    best = grid.iloc[0]
    strategy = MACrossover(int(best.fast), int(best.slow), **exits[best.exit])
    print(f"\nBest in-sample: {strategy}")

    rows = []
    for label, (start, end) in {"In-sample": IN_SAMPLE, "Out-of-sample": OUT_OF_SAMPLE}.items():
        for cost_label, multiplier in (("", 1), (" (2x spread)", 2)):
            results = {p: run_backtest(load_fed_daily(p),
                                       replace(pair_spec(p), spread_pips=pair_spec(p).spread_pips * multiplier), strategy,
                                       start=start, end=end) for p in PAIRS}
            table = summary_table(results)
            row = table.loc["PORTFOLIO"].to_dict()
            row["pairs_profitable"] = f"{int((table.drop(index='PORTFOLIO').total_return > 0).sum())}/8"
            rows.append({"period": label + cost_label, **row})
            if label == "Out-of-sample" and multiplier == 1:
                table.to_csv(RESULTS / "out_of_sample_by_pair.csv", float_format="%.4f")
                print("\nOut-of-sample, per pair:")
                print_table(table)
    periods = pd.DataFrame(rows).set_index("period")
    periods.to_csv(RESULTS / "in_vs_out_of_sample.csv", float_format="%.4f")
    print("\nPortfolio, in-sample vs out-of-sample:")
    print_table(periods)

    full = run_pairs(strategy)
    equity_chart(portfolio_equity(full), OUT_OF_SAMPLE[0], RESULTS / "equity_curve.png",
                 "Portfolio of 8 USD pairs, $10k each, 1% risk per trade")
    heatmap_chart(grid, RESULTS / "sharpe_heatmap.png")
    eur = full["EURUSD"]
    trades_chart(load_fed_daily("EURUSD"), eur.indicators, eur.trades, "EURUSD",
                 "2022-01-01", RESULTS / "eurusd_trades.png")
    all_trades(full).to_csv(RESULTS / "trades_full_history.csv", index=False, float_format="%.5f")
    print(f"\nCharts and CSVs written to {RESULTS}")


def cmd_signals(args) -> None:
    strategy, risk = strategy_from(args), risk_from(args)
    rows = []
    for pair in PAIRS:
        spec = pair_spec(pair)
        bars = load_fed_daily(pair)
        result = run_backtest(bars, spec, strategy, risk)
        last = result.indicators.iloc[-1]
        pos = result.open_position
        row = {"pair": pair, "as_of": bars.index[-1].date(), "close": bars.close.iloc[-1],
               "trend": "up" if last.trend > 0 else "down"}
        if pos:
            row.update(position="LONG" if pos.direction > 0 else "SHORT", since=pos.entry_date.date(),
                       entry=round(pos.entry_price, 5), stop=round(pos.stop, 5), units=f"{int(pos.units):,}")
        else:
            row.update(position="flat")
        if last.signal:
            side = "BUY" if last.signal > 0 else "SELL"
            stop = bars.close.iloc[-1] - last.signal * strategy.stop_atr * last.atr
            row["next_action"] = f"{side} at next open, initial stop {stop:.5f}"
        else:
            row["next_action"] = "hold" if pos else "wait for crossover"
        rows.append(row)
    print(f"Strategy: {strategy}\n")
    print(pd.DataFrame(rows).fillna("").to_string(index=False))
    print("\nStops trail at each daily close. Position sizes assume each pair started at "
          f"${risk.initial_equity:,.0f} in 2005; this is research output, not financial advice.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="backtest one or more pairs")
    bt.add_argument("--pairs", nargs="+", choices=list(PAIRS), type=str.upper)
    bt.add_argument("--start")
    bt.add_argument("--end")
    bt.add_argument("--csv", help="OHLC file to use instead of the bundled Fed data")
    add_strategy_args(bt)
    bt.set_defaults(func=cmd_backtest)

    opt = sub.add_parser("optimize", help="in-sample grid search + out-of-sample test + charts")
    opt.set_defaults(func=cmd_optimize)

    sig = sub.add_parser("signals", help="current positions and next actions")
    add_strategy_args(sig)
    sig.set_defaults(func=cmd_signals)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
