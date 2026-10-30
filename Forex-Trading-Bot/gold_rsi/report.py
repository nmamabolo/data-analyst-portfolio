"""Chart: the trader's rule on gold, sells vs buys, against the gold price.  python -m gold_rsi.report"""
import pandas as pd

from forexbot.report import INK, MUTED, SERIES, _save, plt

from .lab import COSTS, RESULTS, load_m1


def main(cost: float = COSTS["typical_cost"]):
    t = pd.read_csv(RESULTS / "traders_rule_trades.csv", parse_dates=["entry_time", "exit_time"])
    t["net"] = t.gross_usd - cost - t.financing_usd
    t = t.sort_values("exit_time")
    price = load_m1().close.resample("1D").last().dropna()

    fig, (ax_p, ax) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.6], "hspace": 0.1})
    ax_p.plot(price.index, price, color=MUTED, linewidth=1.2)
    ax_p.set_ylabel("Gold (USD/oz)")
    ax_p.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax_p.set_title("Gold M15, RSI(14): sell at 80, buy at 20, 0.01 lot, after costs")

    for color, (label, part) in zip(SERIES, (("Sells at RSI 80", t[t.side < 0]), ("Buys at RSI 20", t[t.side > 0]),
                                             ("All trades", t))):
        eq = part.set_index("exit_time").net.cumsum()
        ax.step(eq.index, eq, where="post", color=color, linewidth=2 if label == "All trades" else 1.6)
        v = eq.iloc[-1]
        ax.text(eq.index[-1], v, rf"  {label}: {'+' if v >= 0 else '−'}\${abs(v):,.0f}", color=INK, fontsize=9, va="center")
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.axhline(-600, color=INK, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(price.index[0], -600, r" A R10,000 account (≈ \$600) is gone below this line", color=INK, fontsize=9, va="bottom")
    ax.set_ylabel("Cumulative profit (USD)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlim(price.index[0], price.index[-1] + pd.Timedelta(days=420))
    return _save(fig, RESULTS / "traders_rule.png")


if __name__ == "__main__":
    print(main())
