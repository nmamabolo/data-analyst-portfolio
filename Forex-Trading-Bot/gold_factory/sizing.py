"""Lot sizes and account capital for the gold evening rule.

Rule: buy XAU/USD at 20:00 UTC (22:00 South African time), sell at 00:00 UTC (02:00 SA),
every weekday. The trade log (results/evening_rule_trades.csv) is per 0.01 lot = 1 ounce,
after $0.40 spread + commission and a full night's swap. Everything scales linearly with
lot size: 0.10 lot is 10x the profit, the loss and the drawdown of 0.01 lot.

Capital per 0.01 lot is set by the worst historical losing stretch, not by margin:
  aggressive    the worst stretch would cost ~50% of the account
  recommended   the worst stretch would cost ~25% of the account
  conservative  a stretch twice as bad as the worst seen would cost ~25% of the account

  python -m gold_factory.sizing
"""
import numpy as np
import pandas as pd

from .run import RESULTS

USDZAR = 16.67                      # latest rate in this project's data (Oct 2026)
LOTS = [0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.00]
BILLS_ZAR = 15_000


def per_lot_stats(net: pd.Series) -> dict:
    eq = net.cumsum()
    months = net.resample("ME").sum()[net.resample("ME").size() > 0]
    return dict(avg_month_all=months.mean(), avg_month_2025_26=net.loc["2025":].resample("ME").sum().mean(),
                worst_month=months.min(), worst_trade=net.min(),
                max_drawdown=(eq - eq.cummax().clip(lower=0)).min())


def capital_per_001(max_dd: float) -> dict:
    return dict(aggressive=2 * abs(max_dd), recommended=4 * abs(max_dd), conservative=8 * abs(max_dd))


def loss_odds(net: pd.Series, capital: float, months: int = 12, paths: int = 20_000, seed: int = 4):
    """Bootstrap whole months of real trades: chance that a 12-month run ever falls 25% / 50% below its start."""
    m = net.resample("ME").sum()[net.resample("ME").size() > 0].to_numpy()
    rng = np.random.default_rng(seed)
    sims = m[rng.integers(0, len(m), size=(paths, months))].cumsum(axis=1)
    low = sims.min(axis=1)
    return {"p_down_25pct": float((low <= -0.25 * capital).mean()), "p_down_50pct": float((low <= -0.50 * capital).mean()),
            "p_losing_year": float((sims[:, -1] < 0).mean())}


def main():
    trades = pd.read_csv(RESULTS / "evening_rule_trades.csv", parse_dates=["entry_time"]).set_index("entry_time")
    net, gold_price = trades.net_usd, float(trades.buy.iloc[-1])
    s = per_lot_stats(net)
    cap = capital_per_001(s["max_drawdown"])
    rows = []
    for lots in LOTS:
        k = lots / 0.01
        rows.append(dict(lots=lots, avg_month_all_usd=s["avg_month_all"] * k, avg_month_2025_26_usd=s["avg_month_2025_26"] * k,
                         worst_month_usd=s["worst_month"] * k, worst_night_usd=s["worst_trade"] * k,
                         worst_drawdown_usd=s["max_drawdown"] * k, margin_1_100_usd=gold_price * k / 100,
                         capital_aggressive_usd=cap["aggressive"] * k, capital_recommended_usd=cap["recommended"] * k,
                         capital_conservative_usd=cap["conservative"] * k))
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "evening_rule_sizing.csv", index=False, float_format="%.2f")
    odds = {name: {"all_years": loss_odds(net, cap[name]), "2025_26_only": loss_odds(net.loc["2025":], cap[name], seed=5)}
            for name in cap}
    return s, cap, table, odds


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    s, cap, table, odds = main()
    print({k: round(v, 2) for k, v in s.items()}, "| capital per 0.01 lot:", cap)
    show = table.copy()
    for c in [c for c in show if c.endswith("_usd")]:
        show[c.replace("_usd", "_zar")] = show[c] * USDZAR
    print(show[["lots"] + [c for c in show if c.endswith("_zar")]].round(0).to_string(index=False))
    for label, per in (("2025-26 pace", s["avg_month_2025_26"]), ("2020-26 average", s["avg_month_all"])):
        lots = BILLS_ZAR / USDZAR / per * 0.01
        print(f"R{BILLS_ZAR:,}/month at the {label}: {lots:.2f} lot, recommended capital ${cap['recommended'] * lots / 0.01:,.0f} "
              f"(R{cap['recommended'] * lots / 0.01 * USDZAR:,.0f})")
    for name, o in odds.items():
        print(name, {k: {kk: f"{vv:.0%}" for kk, vv in v.items()} for k, v in o.items()})
