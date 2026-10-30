"""Chart: the trader's RSI rule ranked across every market.  python -m markets.report"""
import pandas as pd

from forexbot.report import INK, INK_2, MUTED, SERIES, _save, plt

from .lab import RESULTS


def main():
    r = pd.read_csv(RESULTS / "traders_rule_by_market.csv").sort_values("t_stat")
    fig, ax = plt.subplots(figsize=(9.5, 10))
    ax.axvspan(-2, 2, color=MUTED, alpha=0.12, linewidth=0)
    ax.text(0, -1.3, "Grey band: no different from luck", ha="center", va="center", fontsize=9, color=INK_2)
    colors = [SERIES[1] if "V75" in m else SERIES[0] for m in r.market]
    ax.barh(r.market, r.t_stat, color=colors, height=0.65)
    ax.axvline(0, color=INK_2, linewidth=1)
    for y, (m, tstat, pct) in enumerate(zip(r.market, r.t_stat, r.net_pct_per_year)):
        ax.text(tstat + (0.12 if tstat >= 0 else -0.12), y, f"{pct:+.0f}%/yr", va="center",
                ha="left" if tstat >= 0 else "right", fontsize=8, color=INK)
    ax.set_xlabel("t-statistic of the average trade after costs (above +2 would suggest a real edge)")
    ax.set_title("'Sell at RSI 80, buy at 20' on 34 markets: none beats luck; the random V75 ranks 3rd")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(r.t_stat.min() - 1.5, max(r.t_stat.max(), 2) + 1.2)
    ax.set_ylim(-1.8, len(r) - 0.3)
    return _save(fig, RESULTS / "markets_ranked.png")


if __name__ == "__main__":
    print(main())
