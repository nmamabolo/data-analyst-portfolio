"""Can $10k pay the bills? Simulate payout policies on the portfolio's monthly returns.

Policies (all start with $10,000, money is withdrawn at each month end):
  fixed      withdraw the full bill amount every month from month one
  percent    withdraw `rate` of the account every month
  ladder     the rollover plan: reinvest everything until the account reaches the
             first milestone, then pay `rate` x milestone as a fixed paycheck. Each time
             the account crosses the next milestone (+25%) the paycheck steps up; it
             steps down a level only if the account falls 20% below its milestone.
Optional `deposit`: money added every month until the paycheck starts (a top-up
from a salary while the account is still being built).
Optional `bill_growth`: yearly inflation of the bills. The ladder's first milestone
moves with it, and "covered" means the paycheck meets that month's inflated bill.
"""
import numpy as np
import pandas as pd

START = 10_000.0


def bill_path(months: int, bill: float, bill_growth: float = 0.0) -> np.ndarray:
    return bill * (1 + bill_growth) ** (np.arange(months) / 12)


def run_policy(returns: np.ndarray, policy: str, bill: float = 1_000.0, rate: float = 0.006,
               step: float = 1.25, start: float = START, deposit: float = 0.0, bill_growth: float = 0.0):
    """Returns (equity path, withdrawals path) for one sequence of monthly returns."""
    n = len(returns)
    equity = np.empty(n)
    paid = np.zeros(n)
    bills = bill_path(n, bill, bill_growth)
    eq = start
    first_milestone = None
    level = 0.0   # current milestone the paycheck is based on (0 = still compounding)
    for t, r in enumerate(returns):
        eq *= 1 + r
        if policy == "fixed":
            take = min(bills[t], max(eq, 0))
        elif policy == "percent":
            take = rate * max(eq, 0)
        else:  # ladder
            if level == 0 and eq >= max(start, bills[t] / rate):
                level = first_milestone = max(start, bills[t] / rate)
            if level:
                while eq >= level * step:
                    level *= step
                while level > first_milestone and eq < 0.8 * level:
                    level /= step
                take = min(rate * level, max(eq, 0)) if eq >= 0.8 * first_milestone else 0.0
            else:
                take = 0.0
                eq += deposit
        eq -= take
        paid[t] = take
        equity[t] = eq
    return equity, paid


def block_bootstrap(returns: pd.Series, months: int, n_paths: int, block: int = 12, seed: int = 3):
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    starts = rng.integers(0, len(r) - block, size=(n_paths, months // block + 1))
    paths = np.concatenate([r[s:s + block] for s in starts.ravel()]).reshape(n_paths, -1)
    return paths[:, :months]


def monte_carlo(returns: pd.Series, policy: str, years: int = 10, n_paths: int = 5_000, **kw):
    months = years * 12
    sims = block_bootstrap(returns, months, n_paths)
    eqs, pays = zip(*(run_policy(p, policy, **kw) for p in sims))
    eqs, pays = np.array(eqs), np.array(pays)
    bills = bill_path(months, kw.get("bill", 1_000.0), kw.get("bill_growth", 0.0))
    covers = pays >= bills * 0.999
    first_cover = np.where(covers.any(axis=1), covers.argmax(axis=1) / 12, np.inf)
    full_months = np.where((~covers).any(axis=1), (~covers).argmax(axis=1), months)
    yearly_income = pays.reshape(n_paths, years, 12).sum(axis=2) / 12   # average monthly income each year
    return {
        "policy": policy, **{k: v for k, v in kw.items()},
        "median_years_until_bills_covered": float(np.median(first_cover)),
        "median_months_bills_paid_in_full": float(np.median(full_months)),
        "p_bills_covered_by_year_5": float((first_cover <= 5).mean()),
        "p_bills_covered_by_year_10": float((first_cover <= 10).mean()),
        "median_monthly_income_year1": float(np.median(yearly_income[:, 0])),
        "median_monthly_income_year5": float(np.median(yearly_income[:, 4])),
        "median_monthly_income_year10": float(np.median(yearly_income[:, min(9, years - 1)])),
        "median_monthly_income_final_year": float(np.median(yearly_income[:, -1])),
        "years": years,
        "p_account_below_half_start": float((eqs.min(axis=1) < 0.5 * kw.get("start", START)).mean()),
        "p_account_wiped_out": float((eqs[:, -1] <= 100).mean()),
        "median_final_equity": float(np.median(eqs[:, -1])),
        "total_paid_median": float(np.median(pays.sum(axis=1))),
    }
