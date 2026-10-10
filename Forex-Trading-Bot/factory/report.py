"""Final tables and charts for the strategy factory.  python -m factory.report"""
import numpy as np
import pandas as pd

from forexbot.report import INK, INK_2, MUTED, SERIES, _save, plt

from . import monthly
from .income import START, block_bootstrap, monte_carlo, run_policy
from .portfolio import combine, daily_sleeve, monthly_sleeve, select, survivor_returns
from .run import RESULTS, passes

FINANCING = 0.05      # yearly cost of borrowed exposure above 1x
BILL = 1_000.0        # monthly bills to cover (USD)
RATE = 0.006          # sustainable payout per month (~7.2% a year, below the 9% long-run return)
GROUPS = {"Bitcoin": ["BTCUSD"], "8 FX pairs": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY",
                                                "USDCHF", "USDCAD", "USDZAR"],
          "Oil (WTI, Brent)": ["WTI", "BRENT"], "Cross-market baskets": ["BASKET"]}


def levered(r: pd.Series, k: float) -> pd.Series:
    return k * r - max(k - 1, 0) * FINANCING / 12


def luck_chart(real: pd.DataFrame, null: pd.DataFrame):
    rs, ns = passes(real), passes(null)
    rows = [(g, rs.asset.isin(a).sum(), ns.asset.isin(a).sum(),
             (rs[rs.asset.isin(a)].final_sharpe > 0).mean()) for g, a in GROUPS.items()]
    df = pd.DataFrame(rows, columns=["group", "real", "luck", "final_positive"]).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    y = np.arange(len(df))
    ax.barh(y + 0.19, df.real, height=0.36, color=SERIES[0], label="Passed on real prices")
    ax.barh(y - 0.19, df.luck, height=0.36, color=MUTED, label="Passed on shuffled prices (luck)")
    for yi, (r, l, fp) in enumerate(zip(df.real, df.luck, df.final_positive)):
        ax.text(r + 5, yi + 0.19, f"{r}  ({fp:.0%} profitable 2021-26)" if r else "0", va="center", fontsize=9, color=INK)
        ax.text(l + 5, yi - 0.19, str(l), va="center", fontsize=9, color=INK_2)
    ax.set_yticks(y, df.group)
    ax.set_xlabel("Strategies passing both the 2000-16 and 2017-20 tests (of 33,096 created)")
    ax.set_title("About half the 'winners' are luck; FX survivors then failed on 2021-26 data")
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(df.real.max(), df.luck.max()) * 1.45)
    return _save(fig, RESULTS / "luck_vs_real.png")


def final_test_chart(sleeves: pd.DataFrame):
    x = sleeves.loc["2021-01-01":]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = {"portfolio": "Combined portfolio (10% vol)", "monthly_sleeve": "Monthly S&P 500 + gold trend",
              "daily_sleeve": "12 daily survivors"}
    for color, col in zip(SERIES, ["monthly_sleeve", "portfolio", "daily_sleeve"]):
        eq = START * (1 + x[col]).cumprod()
        ax.plot(eq.index, eq, color=color, linewidth=2)
        ax.text(eq.index[-1], eq.iloc[-1], rf"  {labels[col]}: \${eq.iloc[-1]:,.0f}", color=INK, fontsize=9, va="center")
    ax.axhline(START, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title(r"Final test, 2021 - Sep 2026: \$10k, chosen with 2000-2020 data only")
    ax.set_xlim(x.index[0], x.index[-1] + pd.Timedelta(days=900))
    return _save(fig, RESULTS / "final_test.png")


def ladder_projection(returns: pd.Series, deposit: float, years: int = 30, n_paths: int = 3000):
    sims = block_bootstrap(returns, years * 12, n_paths)
    pays = np.array([run_policy(p, "ladder", bill=BILL, rate=RATE, deposit=deposit)[1] for p in sims])
    monthly_by_year = pays.reshape(n_paths, years, 12).mean(axis=2)
    return np.percentile(monthly_by_year, [10, 50, 90], axis=0)


def income_chart(returns: pd.Series):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    years = np.arange(1, 31)
    nudge = {0: 0, 250: -70, 500: 70}   # keep end labels apart when the medians meet
    for color, dep in zip(SERIES, (0, 250, 500)):
        p10, p50, p90 = ladder_projection(returns, dep)
        ax.plot(years, p50, color=color, linewidth=2)
        ax.fill_between(years, p10, p90, color=color, alpha=0.12, linewidth=0)
        label = r"\$10k only" if dep == 0 else rf"\$10k + \${dep}/month top-up"
        ax.text(30.3, p50[-1] + nudge[dep], label, color=INK, fontsize=9, va="center")
    ax.axhline(BILL, color=INK, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(1, BILL * 1.04, rf"Monthly bills \${BILL:,.0f}", color=INK, fontsize=9)
    ax.set_xlim(1, 37)
    ax.set_xlabel("Year")
    ax.set_ylabel("Monthly paycheck (median, 10-90% band)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("Rollover ladder: compound until the account can pay bills, then step the paycheck up")
    return _save(fig, RESULTS / "income_ladder.png")


def income_tables(returns: pd.Series) -> pd.DataFrame:
    rows = []
    for k in (1.0, 1.5, 2.0):
        r = levered(returns, k)
        rows.append(monte_carlo(r, "fixed", years=10, n_paths=3000, bill=BILL) | {"leverage": k})
        rows.append(monte_carlo(r, "percent", years=10, n_paths=3000, bill=BILL, rate=RATE) | {"leverage": k})
        for dep in (0, 250, 500):
            rows.append(monte_carlo(r, "ladder", years=30, n_paths=3000, bill=BILL, rate=RATE, deposit=dep)
                        | {"leverage": k})
    return pd.DataFrame(rows)


def main():
    real = pd.read_csv(RESULTS / "all_strategies.csv.gz")
    null = pd.read_csv(RESULTS / "luck_control.csv.gz")
    print(luck_chart(real, null))

    survivors = pd.read_csv(RESULTS / "survivors.csv")
    rets = survivor_returns(survivors)
    chosen = select(survivors, rets)
    pd.Series(chosen, name="strategy").to_csv(RESULTS / "chosen_daily_strategies.csv", index=False)
    msleeve, mspec = monthly_sleeve()
    sleeves = combine(daily_sleeve(rets, chosen), msleeve, 0.10)
    sleeves.to_csv(RESULTS / "final_portfolio_monthly_returns.csv", float_format="%.6f")
    print(final_test_chart(sleeves))
    monthly.evaluate().to_csv(RESULTS / "monthly_strategies.csv", index=False, float_format="%.4f")

    # Income plans run on the strategy that actually survived: the monthly sleeve, over 1972-2026.
    base = msleeve.loc["1972-01-01":]
    table = income_tables(base)
    table.to_csv(RESULTS / "income_plans.csv", index=False, float_format="%.4f")
    print(income_chart(base))
    return table


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    t = main()
    cols = ["leverage", "policy", "deposit", "median_months_bills_paid_in_full", "median_years_until_bills_covered",
            "p_bills_covered_by_year_10", "median_monthly_income_year1", "median_monthly_income_year5",
            "median_monthly_income_year10", "median_monthly_income_final_year", "years", "p_account_below_half_start",
            "median_final_equity"]
    print(t.reindex(columns=cols).round(2).to_string(index=False))
