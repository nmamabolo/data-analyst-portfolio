import numpy as np
import pandas as pd
import pytest

from gold_factory.run import hour_positions, net_returns, shuffled, spec_positions

STEP = pd.Timedelta("1h")


def hourly(n=48, start="2024-03-05 00:00", seg=None, seed=0):
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "segment": np.zeros(n, int) if seg is None else seg}, index=idx)


def test_hour_of_day_holds_the_right_bars():
    b = hourly()
    spec = dict(family="hour_of_day", params=dict(start_utc=13, hours=2), direction="short_only")
    p = hour_positions(spec, b.close, STEP)
    held_hours = sorted(set((p[p != 0].index + STEP).hour))
    assert held_hours == [13, 14] and set(p[p != 0]) == {-1.0}


def test_hour_of_day_skips_weekends():
    b = hourly(n=72, start="2024-03-08 00:00")          # Friday to Sunday
    spec = dict(family="hour_of_day", params=dict(start_utc=10, hours=1), direction="long_only")
    p = hour_positions(spec, b.close, STEP)
    assert set((p[p != 0].index + STEP).dayofweek) == {4}


def test_no_return_is_earned_across_a_data_hole():
    seg = np.array([0] * 10 + [1] * 10)
    b = hourly(n=20, seg=seg)
    b.iloc[10:, b.columns.get_loc("close")] *= 1.5       # a 50% jump hidden in the hole
    r = net_returns(pd.Series(1.0, b.index), b, STEP)
    assert abs(r.iloc[10]) < 0.01


def test_positions_are_flat_on_each_segment_end():
    seg = np.array([0] * 30 + [1] * 30)
    b = hourly(n=60, seg=seg)
    spec = dict(family="hour_of_day", params=dict(start_utc=0, hours=24), filter="none", filter_params={},
                direction="long_only", max_hold=0)
    p = spec_positions(spec, b, STEP)
    assert p.iloc[29] == 0 and p.iloc[-1] == 0


def test_shuffle_keeps_the_overall_move():
    b = hourly(n=500)
    s = shuffled(b)
    assert s.close.iloc[-1] == pytest.approx(b.close.iloc[-1], rel=1e-9)
    assert not np.allclose(s.close.to_numpy(), b.close.to_numpy())
