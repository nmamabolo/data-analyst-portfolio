"""The trader's RSI 80/20 flip rule on gold with compounding lot sizes and margin calls.

Rule: one trade at a time on XAU/USD M15. When RSI(14) reaches 80, SELL; hold until RSI
reaches 20, then close and BUY; hold until RSI reaches 80, close and SELL; and so on.
Two versions: no stop-loss (positions only close at the opposite signal), and with the
3 x ATR safety stop used in lab.py.

Compounding: before each trade, lots = floor(equity / capital_per_0.01_lot) x 0.01, never below
0.01 lot. Equity is marked to the worst price inside every bar while a trade is open; if it
reaches the broker stop-out level (50% margin level at 1:500 leverage) the account is closed
out at that price and the run stops - a margin call.

Costs: $0.40 per ounce round trip (spread + commission) and 4% a year financing on the
position's value. Account in USD; R16.67 per dollar for rand figures.

  python -m gold_rsi.compound
"""
import numpy as np
import pandas as pd

from .lab import COSTS, FINANCING, RESULTS, _simulate, bars, load_m1, signals

USDZAR = 16.67
START_ZAR = 10_000
LEVERAGE = 500
STOP_OUT = 0.50                   # margin level at which the broker closes everything
SIZING_ZAR = {"aggressive (0.01 lot per R10,000)": 10_000, "recommended (0.01 lot per R20,000)": 20_000}


def trade_list(b: pd.DataFrame, with_stop: bool) -> pd.DataFrame:
    el, es, xl, xs, end, stop, target = signals(b, "touch", "reverse", "none")
    if not with_stop:
        stop = np.where(stop > 0, b.close.to_numpy() * 10, 0.0)     # a stop that can never be reached
    o, h, l, c = (b[x].to_numpy(np.float64) for x in ("open", "high", "low", "close"))
    ent, ext, side, pnl, why = _simulate(o, h, l, c, el, es, xl, xs, end, stop, target)
    return pd.DataFrame({"ent": ent, "ext": ext, "side": side, "entry": o[ent], "move": pnl, "why": why})


def run_account(b: pd.DataFrame, trades: pd.DataFrame, capital_per_001_zar: float, start: pd.Timestamp,
                start_zar: float = START_ZAR):
    """Walk the trades in order with compounding lot sizes; returns the equity curve and outcome."""
    h, l = b.high.to_numpy(), b.low.to_numpy()
    times = b.index
    equity = start_zar / USDZAR
    per_001 = capital_per_001_zar / USDZAR
    curve, peak, worst_dd, n = [(start, equity)], equity, 0.0, 0
    for tr in trades[times[trades.ent] >= start].itertuples():
        lots = max(0.01, np.floor(equity / per_001) * 0.01)
        ounces = lots * 100
        # worst point while the trade is open (including the exit bar)
        seg = slice(tr.ent, tr.ext + 1)
        worst_move = (l[seg].min() - tr.entry) if tr.side > 0 else (tr.entry - h[seg].max())
        margin = tr.entry * ounces / LEVERAGE
        if equity + worst_move * ounces <= STOP_OUT * margin:
            equity = STOP_OUT * margin
            curve.append((times[tr.ext], equity))
            return pd.DataFrame(curve, columns=["time", "equity"]).set_index("time"), "MARGIN CALL", n + 1, worst_dd
        days = (times[tr.ext] - times[tr.ent]).total_seconds() / 86_400
        cost = COSTS["typical_cost"] * ounces + FINANCING * tr.entry * ounces * days / 365
        equity += tr.move * ounces - cost
        n += 1
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity / peak - 1)
        curve.append((times[tr.ext], equity))
        if equity <= 0:
            return pd.DataFrame(curve, columns=["time", "equity"]).set_index("time"), "WIPED OUT", n, worst_dd
    return pd.DataFrame(curve, columns=["time", "equity"]).set_index("time"), "survived", n, worst_dd


def main(starts_zar=(10_000, 100_000, 1_000_000)):
    b = bars(load_m1(), "15min")
    rows, curves = [], {}
    for with_stop in (False, True):
        t = trade_list(b, with_stop)
        for start_zar in starts_zar:
            for label, cap in SIZING_ZAR.items():
                for year in range(2020, 2026):
                    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
                    curve, outcome, n, dd = run_account(b, t, cap, start, start_zar)
                    final = curve.equity.iloc[-1] * USDZAR
                    yrs = (curve.index[-1] - start).days / 365.25
                    rows.append(dict(stop_loss="3 x ATR" if with_stop else "none", start_zar=start_zar, sizing=label,
                                     start=year, outcome=outcome, trades=n, end=curve.index[-1].date(),
                                     final_zar=final, worst_drawdown=dd,
                                     yearly_growth=(final / start_zar) ** (1 / max(yrs, 0.1)) - 1 if final > 0 else -1.0))
                    curves[(with_stop, start_zar, label, year)] = curve
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "compounding_accounts.csv", index=False, float_format="%.4f")
    return table, curves


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    table, _ = main()
    print(table.round(3).to_string(index=False))


def chart(curves, start_zar: int = 100_000, label: str = "recommended (0.01 lot per R20,000)", year: int = 2020):
    from forexbot.report import INK, MUTED, SERIES, _save, plt
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for color, (with_stop, name) in zip(SERIES, ((False, "No stop-loss"), (True, "3 x ATR stop-loss"))):
        c = curves[(with_stop, start_zar, label, year)].equity * USDZAR
        ax.step(c.index, c, where="post", color=color, linewidth=1.8)
        end = c.index[-1]
        tag = "margin call" if c.iloc[-1] < start_zar * 0.01 else f"R{c.iloc[-1]:,.0f}"
        ax.text(end, c.iloc[-1], f"  {name}: {tag}", color=INK, fontsize=9, va="center")
    ax.axhline(start_zar, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(c.index[0], start_zar * 1.03, f" Start R{start_zar:,}", color=INK, fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R{v:,.0f}"))
    ax.set_ylabel("Account balance")
    ax.set_title(f"Gold M15, sell at RSI 80 / buy at 20, one trade at a time, lots grow with the account (start {year})")
    ax.set_xlim(c.index[0], c.index[-1] + pd.Timedelta(days=500))
    return _save(fig, RESULTS / "compounding_account.png")
