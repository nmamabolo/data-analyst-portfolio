"""The income plan in rand: R15,000 a month of bills.

The strategy holds dollar assets (S&P 500 and gold), so the simulation runs in
USD and converts at the latest USD/ZAR rate in the data. Bills grow 3% a year in
dollar terms, roughly SA inflation (~5-6%) less the rand's usual yearly slide
against the dollar. All rand figures are reported in today's money. The headline
case starts with R10,000; a $10,000 start is kept for comparison.

  python -m factory.rand_plan
"""
import numpy as np
import pandas as pd

from forexbot.data import load_fed_daily
from forexbot.report import INK, SERIES, _save, plt

from .income import bill_path, block_bootstrap, monte_carlo, run_policy
from .portfolio import monthly_sleeve
from .run import RESULTS

BILLS_ZAR = 15_000
INFLATION_USD = 0.03         # yearly growth of the bills measured in dollars
RATE = 0.005                 # payout per month: ~6% a year = ~9% return minus 3% inflation
YEARS = 40
SA_FINANCING = 0.10          # borrowing in rand costs about prime (~10%); shown once for comparison
STARTS_ZAR = {"R10,000": 10_000, "$10,000": None}
TOPUPS_ZAR = [0, 2_500, 5_000, 10_000, 20_000]
CHART_TOPUPS = [2_500, 5_000, 10_000, 20_000]
START_ZAR = 10_000


def usdzar() -> tuple[float, str]:
    s = load_fed_daily("USDZAR").close
    return float(s.iloc[-1]), s.index[-1].strftime("%d %b %Y")


def plans():
    fx, fx_date = usdzar()
    base, _ = monthly_sleeve()
    base = base.loc["1972-01-01":]
    bill = BILLS_ZAR / fx
    rows = []
    for label, zar in STARTS_ZAR.items():
        start = 10_000.0 if zar is None else zar / fx
        common = dict(years=YEARS, n_paths=3000, bill=bill, bill_growth=INFLATION_USD, start=start)
        rows.append(monte_carlo(base, "fixed", **common) | {"start_label": label, "topup_zar": 0, "leverage": 1})
        rows.append(monte_carlo(base, "percent", rate=RATE, **common)
                    | {"start_label": label, "topup_zar": 0, "leverage": 1})
        for top in TOPUPS_ZAR:
            rows.append(monte_carlo(base, "ladder", rate=RATE, deposit=top / fx, **common)
                        | {"start_label": label, "topup_zar": top, "leverage": 1})
    lev = 1.5 * base - 0.5 * SA_FINANCING / 12
    rows.append(monte_carlo(lev, "ladder", rate=RATE, deposit=5_000 / fx, years=YEARS, n_paths=3000, bill=bill,
                            bill_growth=INFLATION_USD, start=START_ZAR / fx)
                | {"start_label": "R10,000", "topup_zar": 5_000, "leverage": 1.5})
    t = pd.DataFrame(rows)
    t["usdzar"], t["usdzar_date"] = fx, fx_date
    # Real (today's-rand) income: deflate by the bill growth, convert at today's rate.
    for col in [c for c in t if c.startswith("median_monthly_income")]:
        yr = {"year1": 1, "year5": 5, "year10": 10, "final_year": YEARS}[col.removeprefix("median_monthly_income_")]
        t[col.replace("income", "income_zar_today")] = t[col] * fx / (1 + INFLATION_USD) ** (yr - 0.5)
    return t


def chart(fx: float):
    base, _ = monthly_sleeve()
    base = base.loc["1972-01-01":]
    bill = BILLS_ZAR / fx
    years = np.arange(1, YEARS + 1)
    deflate = (1 + INFLATION_USD) ** (years - 0.5)
    sims = block_bootstrap(base, YEARS * 12, 2000)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for color, top in zip(SERIES + ["#eda100"], CHART_TOPUPS):
        pays = np.array([run_policy(p, "ladder", bill=bill, rate=RATE, deposit=top / fx, start=START_ZAR / fx,
                                    bill_growth=INFLATION_USD)[1] for p in sims])
        real = pays.reshape(len(sims), YEARS, 12).mean(axis=2) * fx / deflate
        p10, p50, p90 = np.percentile(real, [10, 50, 90], axis=0)
        ax.plot(years, p50, color=color, linewidth=2)
        ax.fill_between(years, p10, p90, color=color, alpha=0.10, linewidth=0)
        label = f"R10k + R{top:,}/month"
        ax.text(YEARS + 0.4, p50[-1] + {2_500: -1_300, 5_000: -700, 10_000: 600, 20_000: 2_200}[top], label,
                color=INK, fontsize=9, va="center",
                bbox=dict(facecolor=ax.get_facecolor(), edgecolor="none", pad=1))
    ax.axhline(BILLS_ZAR, color=INK, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(1, BILLS_ZAR * 1.03, "Bills R15,000 (today's money)", color=INK, fontsize=9)
    ax.set_xlim(1, YEARS + 9)
    ax.set_xlabel("Year")
    ax.set_ylabel("Monthly paycheck, today's rand")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R{v:,.0f}"))
    ax.text(1, 1_000, "R10k with no top-up: still R0 after 40 years", color=INK, fontsize=9)
    ax.set_title("Start with R10,000: how long until the paycheck covers R15,000 of bills?")
    return _save(fig, RESULTS / "rand_plan.png")


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    t = plans()
    t.to_csv(RESULTS / "rand_plan.csv", index=False, float_format="%.4f")
    print(f"USD/ZAR {t.usdzar.iloc[0]:.4f} on {t.usdzar_date.iloc[0]}; bills = ${BILLS_ZAR / t.usdzar.iloc[0]:,.0f}/month")
    cols = ["start_label", "policy", "topup_zar", "leverage", "median_months_bills_paid_in_full",
            "median_years_until_bills_covered", "p_bills_covered_by_year_10", "p_bills_covered_by_year_5",
            "median_monthly_income_zar_today_year1", "median_monthly_income_zar_today_year10",
            "median_monthly_income_zar_today_final_year", "p_account_below_half_start"]
    print(t[cols].round(2).to_string(index=False))
    print(chart(t.usdzar.iloc[0]))
