"""Static charts for the README (light theme, reference data-viz palette)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from .metrics import drawdown  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
DIVERGING = LinearSegmentedColormap.from_list(
    "blue_gray_red", ["#e34948", "#f0efec", "#2a78d6"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": BASELINE,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def equity_chart(equity: pd.Series, split_date, path: Path, title: str) -> Path:
    fig, (ax, ax_dd) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.08})
    ax.plot(equity.index, equity, color=SERIES[0], linewidth=1.6)
    ax.set_title(title)
    ax.set_ylabel("Portfolio equity (USD)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("${x:,.0f}"))

    dd = drawdown(equity) * 100
    ax_dd.fill_between(dd.index, dd, 0, color=SERIES[0], alpha=0.35, linewidth=0)
    ax_dd.plot(dd.index, dd, color=SERIES[0], linewidth=0.8)
    ax_dd.set_ylabel("Drawdown (%)")
    ax_dd.xaxis.set_major_locator(mdates.YearLocator(2))
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    split = pd.Timestamp(split_date)
    for a in (ax, ax_dd):
        a.axvline(split, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    top = ax.get_ylim()[1]
    ax.text(split, top, "  Out-of-sample: never seen while tuning →", color=INK_2,
            va="top", ha="left", fontsize=9)
    ax.text(split, top, "← In-sample: parameters tuned here  ", color=INK_2,
            va="top", ha="right", fontsize=9)
    return _save(fig, path)


def heatmap_chart(grid: pd.DataFrame, path: Path) -> Path:
    exits = list(dict.fromkeys(grid["exit"]))
    limit = np.nanmax(np.abs(grid["median_pair_sharpe"]))
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    fig, axes = plt.subplots(1, len(exits), figsize=(3.6 * len(exits) + 1, 4.0), squeeze=False)
    for n, (ax, exit_name) in enumerate(zip(axes[0], exits)):
        table = (grid[grid["exit"] == exit_name]
                 .pivot(index="fast", columns="slow", values="median_pair_sharpe")
                 .sort_index(ascending=False))
        image = ax.imshow(table.to_numpy(dtype=float), cmap=DIVERGING, norm=norm, aspect="auto")
        ax.set_xticks(range(len(table.columns)), table.columns)
        ax.set_yticks(range(len(table.index)), table.index)
        ax.set_xlabel("Slow EMA (days)")
        if n == 0:
            ax.set_ylabel("Fast EMA (days)")
        ax.set_title(exit_name, fontsize=10)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for (r, c), value in np.ndenumerate(table.to_numpy(dtype=float)):
            if not np.isnan(value):
                ax.text(c, r, f"{value:.2f}", ha="center", va="center", fontsize=9, color=INK)
    fig.suptitle("Median Sharpe across 8 pairs, 2005–2018: trailing stops beat fixed targets",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)
    bar = fig.colorbar(image, ax=axes[0].tolist(), shrink=0.85, pad=0.02)
    bar.set_label("Median Sharpe ratio", color=INK_2)
    bar.outline.set_visible(False)
    return _save(fig, path)


def trades_chart(bars: pd.DataFrame, indicators: pd.DataFrame, trades: pd.DataFrame,
                 pair: str, since, path: Path) -> Path:
    bars, ind = bars.loc[since:], indicators.loc[since:]
    trades = trades[trades.entry_date >= pd.Timestamp(since)] if len(trades) else trades
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(bars.index, bars["close"], color=MUTED, linewidth=1, label=f"{pair} daily fixing")
    ax.plot(ind.index, ind["fast_ma"], color=SERIES[0], linewidth=1.6, label="Fast EMA")
    ax.plot(ind.index, ind["slow_ma"], color=SERIES[1], linewidth=1.6, label="Slow EMA")
    for direction, marker, label in (("long", "^", "Buy entry"), ("short", "v", "Sell entry")):
        subset = trades[trades.direction == direction] if len(trades) else trades
        if len(subset):
            ax.scatter(subset.entry_date, subset.entry_price, marker=marker, s=60, color=INK,
                       edgecolor=SURFACE, linewidth=1.5, zorder=3, label=label)
    ax.set_title(f"{pair}: the robot buys when the fast EMA crosses above the slow EMA, sells below")
    ax.legend(frameon=False, loc="upper left", ncol=5, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    return _save(fig, path)
