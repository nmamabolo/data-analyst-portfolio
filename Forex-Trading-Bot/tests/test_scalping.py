import numpy as np
import pandas as pd
import pytest

from scalping.engine import score, simulate
from scalping.million import required_sharpe, simulate_years
from scalping.strategies import between, first_per_day

P = 0.0001


def bars(rows):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range("2024-01-02 08:00", periods=len(df), freq="1min", tz="UTC")
    return df


def run(b, signal_at=0, direction=1, stop=5 * P, target=5 * P, flat=None, max_hold=10_000):
    n = len(b)
    sig = np.zeros(n, np.int8)
    sig[signal_at] = direction
    flat = np.zeros(n, bool) if flat is None else flat
    return simulate(b, sig, np.full(n, stop), np.full(n, target), flat, max_hold)


FLAT_BAR = [1.1000, 1.1001, 1.0999, 1.1000]


def test_enters_at_next_open_and_hits_target():
    b = bars([FLAT_BAR, [1.1002, 1.1003, 1.1001, 1.1002], [1.1002, 1.1008, 1.1001, 1.1007]])
    t = run(b).iloc[0]
    assert t.entry_time == b.index[1]
    assert t.exit_reason == "target"
    assert t.gross_pips == pytest.approx(5.0)


def test_stop_wins_when_bar_touches_both():
    b = bars([FLAT_BAR, [1.1000, 1.1001, 1.0999, 1.1000], [1.1000, 1.1010, 1.0990, 1.1000]])
    t = run(b).iloc[0]
    assert t.exit_reason == "stop"
    assert t.gross_pips == pytest.approx(-5.0)


def test_gap_through_stop_fills_at_open():
    b = bars([FLAT_BAR, [1.1000, 1.1001, 1.0999, 1.1000], [1.0980, 1.0982, 1.0978, 1.0980]])
    t = run(b).iloc[0]
    assert t.gross_pips == pytest.approx(-20.0)


def test_short_trade_profits_when_price_falls():
    b = bars([FLAT_BAR, [1.1000, 1.1001, 1.0999, 1.1000], [1.1000, 1.1001, 1.0990, 1.0992]])
    t = run(b, direction=-1).iloc[0]
    assert t.exit_reason == "target"
    assert t.gross_pips == pytest.approx(5.0)


def test_session_close_exits_at_open():
    b = bars([FLAT_BAR, FLAT_BAR, [1.1003, 1.1004, 1.1002, 1.1003]])
    flat = np.array([False, False, True])
    t = run(b, stop=50 * P, target=50 * P, flat=flat).iloc[0]
    assert t.exit_reason == "session"
    assert t.gross_pips == pytest.approx(3.0)


def test_time_stop_exits_at_close():
    b = bars([FLAT_BAR] * 3 + [[1.1000, 1.1001, 1.0999, 1.1001]])
    t = run(b, stop=50 * P, target=50 * P, max_hold=2).iloc[0]
    assert t.exit_reason == "time"
    assert t.bars_held == 2


def test_costs_are_subtracted_per_trade():
    trades = pd.DataFrame({"entry_time": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                           "gross_pips": [2.0, -1.0], "risk_pips": [5.0, 5.0]})
    assert score(trades, 1.0)["net_pips_per_trade"] == pytest.approx(-0.5)


def test_session_window_wraps_midnight():
    m = pd.Series([23 * 60, 30, 12 * 60])
    assert list(between(m, "22:00", "02:00")) == [True, True, False]


def test_first_signal_per_day_only():
    idx = pd.date_range("2024-01-02", periods=4, freq="h")
    b = pd.DataFrame({"day": pd.to_datetime(["2024-01-02"] * 2 + ["2024-01-03"] * 2)}, index=idx)
    assert list(first_per_day(b, np.array([True, True, False, True]))) == [True, False, False, True]


def test_leverage_cap_limits_loss_per_trade():
    # One certain 100-pip loss risking 100% of equity: 30:1 caps the loss at 30*0.01/1.10 = 27%.
    final, _ = simulate_years(np.array([-100.0]), np.array([10.0]), 1, risk=1.0, leverage=30)
    assert final[0] == pytest.approx(10_000 * (1 - 30 * 0.01 / 1.10))


def test_required_sharpe_for_100x():
    assert required_sharpe(100) == pytest.approx(3.035, abs=0.01)
