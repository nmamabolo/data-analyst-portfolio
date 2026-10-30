"""Gold factory follow-up: the time-of-day pattern and the "evening long" rule in dollars.

  python -m gold_factory.report
"""
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

from forexbot.report import DIVERGING, INK, INK_2, SERIES, _save, plt
from gold_rsi.lab import COSTS, FINANCING, bars, load_m1

from .run import RESULTS

PERIODS = {"2020-22 (discover)": "discover_sharpe", "2023-24 (confirm)": "confirm_sharpe",
           "2025-26 (final test)": "final_sharpe"}


def heatmap():
    real = pd.read_csv(RESULTS / "all_strategies.csv.gz")
    h = real[(real.family == "hour_of_day") & (real.timeframe == "M15") & real.spec.str.contains("long_only")
             & real.spec.str.contains("hours=4")].copy()
    h["start"] = h.spec.str.extract(r"start_utc=(\d+)")[0].astype(int)
    grid = h.set_index("start").sort_index()[list(PERIODS.values())].T
    fig, ax = plt.subplots(figsize=(11, 2.9))
    lim = np.nanmax(np.abs(grid.to_numpy()))
    ax.imshow(grid.to_numpy(), cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_yticks(range(3), list(PERIODS))
    ax.set_xticks(range(24), [f"{h:02d}" for h in grid.columns])
    ax.set_xlabel("Start of the 4-hour long window (UTC; add 2 hours for South African time)")
    for (r, c), v in np.ndenumerate(grid.to_numpy()):
        ax.text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=7.5, color=INK)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Holding gold long 4 hours a day: only the evening (19-22 UTC) turned strongly positive, and only from 2023")
    return _save(fig, RESULTS / "time_of_day_heatmap.png")


def evening_trades(start_hour: int = 20, hours: int = 4) -> pd.DataFrame:
    """Buy at the open of the 20:00 UTC bar, sell 4 hours later, every weekday, 1 ounce (0.01 lot).
    Costs: $0.40 spread + commission and one full night's financing, because the window
    crosses the 21:00/22:00 UTC rollover when brokers charge swap."""
    b = bars(load_m1(), "15min")
    days = pd.unique(b.index[(b.index.hour == start_hour) & (b.index.minute == 0) & (b.index.dayofweek < 5)].normalize())
    rows = []
    for d in days:
        t0, t1 = d + pd.Timedelta(hours=start_hour), d + pd.Timedelta(hours=start_hour + hours)
        if t0 in b.index and t1 in b.index and b.segment[t0] == b.segment[t1]:
            rows.append((t0, b.open[t0], b.open[t1]))
    t = pd.DataFrame(rows, columns=["entry_time", "buy", "sell"])
    t["gross_usd"] = t.sell - t.buy
    t["net_usd"] = t.gross_usd - COSTS["typical_cost"] - FINANCING * t.buy / 365
    return t


def by_year_chart(t: pd.DataFrame):
    yr = t.groupby(t.entry_time.dt.year).net_usd.sum()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(yr.index.astype(str), yr.values, color=SERIES[0], width=0.6)
    ax.axhline(0, color=INK_2, linewidth=1)
    for x, v in zip(yr.index.astype(str), yr.values):
        ax.text(x, v + (15 if v >= 0 else -15), f"{'+' if v >= 0 else '−'}${abs(v):,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9, color=INK)
    ax.set_ylim(min(yr.min(), 0) * 1.4, yr.max() * 1.18)
    if 2025 in yr.index:
        ax.text(list(yr.index).index(2025), yr[2025] + yr.max() * 0.12, "missing ~4 months\nof data", ha="center",
                fontsize=8.5, color=INK_2)
    ax.set_ylabel("Profit per year, 0.01 lot (USD)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("'Buy gold at 20:00 UTC, sell at 00:00': nothing until 2025, then strong (2026 = to Oct)")
    ax.grid(axis="x", visible=False)
    return _save(fig, RESULTS / "evening_rule_by_year.png")


def main():
    print(heatmap())
    t = evening_trades()
    t.to_csv(RESULTS / "evening_rule_trades.csv", index=False, float_format="%.4f")
    print(by_year_chart(t))
    return t


if __name__ == "__main__":
    main()
