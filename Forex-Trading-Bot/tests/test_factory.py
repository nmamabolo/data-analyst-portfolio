import numpy as np
import pandas as pd
import pytest

from factory.generator import positions, random_specs, raw_signal
from factory.income import run_policy
from factory.run import strategy_returns

DATES = pd.bdate_range("2023-01-02", periods=300)


def walk(seed=1):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(DATES)))), DATES)


def test_specs_are_unique_and_reproducible():
    a, b = random_specs(500, 96), random_specs(500, 96)
    assert a == b
    assert len({repr(s) for s in a}) == 596


def test_no_lookahead_on_random_specs():
    close, vix = walk(), walk(2) / 5
    for spec in random_specs(300, 0, seed=9):
        full = positions(spec, close, vix).iloc[:200]
        part = positions(spec, close.iloc[:200], vix.iloc[:200])
        np.testing.assert_allclose(full.to_numpy(), part.to_numpy())


def test_position_earns_next_day_return_minus_costs():
    close = pd.Series([100.0, 101.0, 102.01, 100.99], DATES[:4])
    pos = pd.Series([1.0, 1.0, 0.0, 0.0], DATES[:4])
    r = strategy_returns(pos, close.pct_change(), "EURUSD")
    trade, hold = 0.0001, 0.01 / 252
    assert r.iloc[1] == pytest.approx(0.01 - trade - hold)        # bought at day-0 close
    assert r.iloc[2] == pytest.approx(0.01 - hold)                # still long
    assert r.iloc[3] == pytest.approx(-trade)                     # sold at day-2 close, no exposure


def test_turn_of_month_holds_last_and_first_days():
    s = raw_signal("turn_of_month", dict(before=2, after=3), walk(), walk())
    held_into = s[s == 1].index + pd.offsets.BDay(1)
    jan_feb = held_into[(held_into >= "2023-01-25") & (held_into <= "2023-02-08")]
    assert [d.strftime("%m-%d") for d in jan_feb] == ["01-30", "01-31", "02-01", "02-02", "02-03"]


def test_weekday_signal_targets_the_next_session():
    s = raw_signal("weekday", dict(day=0), walk(), walk())          # hold into Mondays
    assert set((s[s == 1].index + pd.offsets.BDay(1)).dayofweek) == {0}


def test_fixed_policy_withdraws_bill_and_can_run_dry():
    equity, paid = run_policy(np.zeros(12), "fixed", bill=1_000)
    assert paid[:10].tolist() == [1_000] * 10
    assert equity[-1] == pytest.approx(0)


def test_ladder_compounds_until_first_milestone_then_steps_up():
    # 5% a month: grows from $10k to the $20k milestone (bill 120 / 0.6% rate), then pays.
    equity, paid = run_policy(np.full(60, 0.05), "ladder", bill=120, rate=0.006)
    first = np.argmax(paid > 0)
    assert paid[:first].sum() == 0 and equity[first - 1] < 20_000 <= equity[first] + paid[first]
    assert paid[first] == pytest.approx(120)
    assert paid[-1] > paid[first]           # paycheck has stepped up since
    assert np.all(np.diff(paid[first:]) >= -1e-9)   # never cut while the account keeps growing


def test_deposits_stop_once_the_paycheck_starts():
    equity, paid = run_policy(np.zeros(40), "ladder", bill=120, rate=0.006, deposit=500)
    first = np.argmax(paid > 0)
    assert equity[first - 1] == pytest.approx(10_000 + 500 * first)   # reached the $20k milestone by saving
    assert paid[first] == pytest.approx(120)
    assert equity[-1] == pytest.approx(equity[first] - 120 * (len(paid) - first - 1))
