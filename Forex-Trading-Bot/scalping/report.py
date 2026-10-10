"""Charts for the scalping study.  python -m scalping.report"""
import numpy as np
import pandas as pd

from forexbot.report import BASELINE, INK, INK_2, MUTED, SERIES, _save, plt

from .lab import RESULTS
from .million import GOAL, START, simulate_years


def edge_chart(summary: pd.DataFrame):
    oos = (summary[(summary.period == "out_of_sample") & (summary.cost == "no_cost")]
           .set_index("strategy")["net_pips_per_trade"].sort_values())
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.barh(oos.index, oos.values, color=SERIES[0], height=0.6)
    ax.axvline(0, color=BASELINE, linewidth=1)
    for x, label in ((0.6, "Best ECN cost 0.6 pip"), (1.0, "Typical cost 1.0 pip")):
        ax.axvline(x, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(x, -0.75, f" {label}", color=INK_2, fontsize=9, va="center")
    for y, v in enumerate(oos.values):
        ax.text(v + (0.03 if v >= 0 else -0.03), y, f"{v:+.2f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=9, color=INK,
                bbox=dict(facecolor=ax.get_facecolor(), edgecolor="none", pad=1))
    ax.set_xlabel("Average profit per trade before costs (pips), 2023–2025 out-of-sample")
    ax.set_title("Only one setup out-earns its trading costs, and it is a 6-hour day trade, not a scalp")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(min(-0.4, oos.min() - 0.2), 1.45)
    ax.set_ylim(-1.1, len(oos) - 0.4)
    return _save(fig, RESULTS / "scalping_edge.png")


def outcomes_chart(name="london_breakout", risk=0.20, leverage=500, cost=0.6):
    trades = pd.read_csv(RESULTS / f"oos_trades_{name}.csv.gz", parse_dates=["entry_time"])
    years = (trades.entry_time.iloc[-1] - trades.entry_time.iloc[0]).days / 365.25
    final, _ = simulate_years(trades.gross_pips.to_numpy() - cost, trades.risk_pips.to_numpy(),
                              int(round(len(trades) / years)), risk, leverage)
    shown = np.clip(final, 1, None)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.hist(shown, bins=np.logspace(0, 7, 57), color=SERIES[0], edgecolor="white", linewidth=1)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    for x, label in ((START, "Start $10k"), (GOAL, "Goal $1M")):
        ax.axvline(x, color=INK, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(x, ax.get_ylim()[1] * 0.97, f" {label}", color=INK, fontsize=9, va="top")
    ruin, hit, median = (final <= 0.1 * START).mean(), (final >= GOAL).mean(), np.median(final)
    ax.text(0.01, 0.80, f"{ruin:.0%} of years lose 90%+\nmedian year ends at ${median:,.0f}\n"
                        f"{hit:.2%} reach $1M ({int(hit * len(final))} of {len(final):,})",
            transform=ax.transAxes, fontsize=9.5, color=INK_2, va="top")
    ax.set_xlabel("Account value after one year (log scale; $1 floor)")
    ax.set_ylabel("Simulated years")
    ax.set_title(f"$10k at {risk:.0%} risk per trade, {leverage}:1 leverage: 10,000 simulated years")
    return _save(fig, RESULTS / "million_outcomes.png")


if __name__ == "__main__":
    summary = pd.read_csv(RESULTS / "summary.csv")
    print(edge_chart(summary))
    print(outcomes_chart())
