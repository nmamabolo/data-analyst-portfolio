import numpy as np
import pandas as pd
import pytest

from gold_rsi.lab import FINANCING, _simulate, bars

IDX = pd.date_range("2024-01-02", periods=6, freq="15min", tz="UTC")


def run(rows, el=(), es=(), xl=(), xs=(), end=(), stop=10.0, target=0.0):
    a = np.array(rows, dtype=float)
    n = len(a)
    f = lambda at: np.isin(np.arange(n), list(at))
    return _simulate(a[:, 0], a[:, 1], a[:, 2], a[:, 3], f(el), f(es), f(xl), f(xs), f(end),
                     np.full(n, stop), np.full(n, target))


def test_target_fills_at_level():
    ent, ext, side, pnl, why = run([[100, 101, 99, 100], [100, 101, 99, 100], [100, 106, 99, 105]],
                                   el=[0], stop=10.0, target=5.0)
    assert pnl[0] == pytest.approx(5.0) and why[0] == 2


def test_stop_beats_target_in_the_same_bar():
    ent, ext, side, pnl, why = run([[100, 101, 99, 100], [100, 101, 99, 100], [100, 106, 89, 100]],
                                   el=[0], stop=10.0, target=5.0)
    assert pnl[0] == pytest.approx(-10.0) and why[0] == 0


def test_reverse_exit_flips_at_the_same_open():
    rows = [[100, 101, 99, 100], [100, 101, 99, 100], [100, 101, 99, 100], [103, 104, 102, 103],
            [106, 107, 105, 106]]
    ent, ext, side, pnl, why = run(rows, es=[0], xs=[2], el=[2], xl=[3], stop=50.0)
    assert list(side) == [-1, 1]
    assert pnl[0] == pytest.approx(-3.0) and ent[1] == ext[0] == 3
    assert pnl[1] == pytest.approx(3.0)       # the flipped long, closed at the next open


def test_position_closed_at_last_close_before_a_data_gap():
    rows = [[100, 101, 99, 100], [100, 101, 99, 100], [100, 103, 99, 102], [200, 201, 199, 200]]
    ent, ext, side, pnl, why = run(rows, el=[0], end=[2], stop=50.0)
    assert why[0] == 3 and pnl[0] == pytest.approx(2.0) and ext[0] == 2
    assert len(pnl) == 1      # no new trade straight after the hole


def test_segments_split_on_long_gaps_only():
    idx = pd.DatetimeIndex(["2024-01-05 20:00", "2024-01-07 23:00", "2024-01-08 00:00", "2024-02-20 00:00"], tz="UTC")
    m1 = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    assert list(bars(m1, "1h").segment) == [0, 0, 0, 1]      # weekend kept, six-week hole split


def test_financing_rate_is_yearly():
    assert FINANCING * 4000 * 365 / 365 == pytest.approx(160)   # $160 a year on one ounce at $4,000


def test_server_clock_is_converted_to_utc():
    from gold_rsi.lab import to_utc
    stamps = pd.DatetimeIndex(["2024-12-06 15:30", "2024-07-05 15:30", "2025-10-03 12:30"])
    # US jobs data at 08:30 New York: 13:30 UTC in winter, 12:30 in summer; later files are already UTC
    assert [t.strftime("%H:%M") for t in to_utc(stamps)] == ["13:30", "12:30", "12:30"]


def test_compounding_account_hits_margin_call_on_a_runaway_loss():
    from gold_rsi.compound import run_account
    idx = pd.date_range("2024-01-02", periods=6, freq="15min", tz="UTC")
    b = pd.DataFrame({"open": 2000.0, "high": [2000, 2000, 2700, 2700, 2700, 2700], "low": 2000.0,
                      "close": 2000.0, "segment": 0}, index=idx)
    trades = pd.DataFrame({"ent": [1], "ext": [5], "side": [-1], "entry": [2000.0], "move": [-700.0], "why": [1]})
    curve, outcome, n, dd = run_account(b, trades, 10_000, idx[0], start_zar=10_000)     # ~$600 account, short 1 oz
    assert outcome == "MARGIN CALL" and n == 1
