import numpy as np
import pandas as pd
import pytest

from rsi_ichimoku.lab import crosses_up, ichimoku, rsi, score, simulate

IDX = pd.date_range("2024-01-02", periods=8, freq="h", tz="UTC")


def frame(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=IDX[:len(rows)], dtype=float)


def flags(n, at):
    a = np.zeros(n, bool)
    for i in at:
        a[i] = True
    return a


def test_entry_and_signal_exit_fill_at_next_open():
    b = frame([[100, 101, 99, 100], [101, 102, 100, 101], [103, 104, 102, 103], [104, 105, 103, 104]])
    n = len(b)
    sig = (flags(n, [0]), flags(n, []), flags(n, [2]), flags(n, []))
    t = simulate(b, sig, np.full(n, 50.0)).iloc[0]
    assert t.entry_time == IDX[1] and t.exit_time == IDX[3]
    assert t.gross_return == pytest.approx(104 / 101 - 1)
    assert t.exit_reason == "signal"


def test_stop_is_hit_inside_the_bar_for_shorts():
    b = frame([[100, 101, 99, 100], [100, 101, 99, 100], [100, 106, 99, 105]])
    n = len(b)
    sig = (flags(n, []), flags(n, [0]), flags(n, []), flags(n, []))
    t = simulate(b, sig, np.full(n, 5.0)).iloc[0]
    assert t.exit_reason == "stop" and t.gross_return == pytest.approx(-0.05)


def test_gap_through_stop_fills_at_open():
    b = frame([[100, 101, 99, 100], [100, 101, 99, 100], [90, 91, 89, 90]])
    n = len(b)
    sig = (flags(n, [0]), flags(n, []), flags(n, []), flags(n, []))
    t = simulate(b, sig, np.full(n, 5.0)).iloc[0]
    assert t.gross_return == pytest.approx(-0.10)


def test_ichimoku_cloud_is_shifted_forward_by_kijun():
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, 200))
    b = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close},
                     index=pd.date_range("2024-01-01", periods=200, freq="h"))
    ich = ichimoku(b, 5, 2, 52)
    mid52 = (b.high.rolling(52).max() + b.low.rolling(52).min()) / 2
    span_a = ((ich.tenkan + ich.kijun) / 2)
    i = 150
    expected = sorted([span_a.iloc[i - 2], mid52.iloc[i - 2]])
    assert [ich.cloud_bottom.iloc[i], ich.cloud_top.iloc[i]] == pytest.approx(expected)


def test_rsi_extremes_and_cross_detection():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert rsi(up, 14).iloc[-1] == pytest.approx(100)
    x = pd.Series([15.0, 19.0, 21.0, 25.0, 18.0, 22.0])
    assert list(crosses_up(x, 20)) == [False, False, True, False, False, True]


def test_score_charges_cost_per_trade():
    t = pd.DataFrame({"entry_time": pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True),
                      "exit_time": pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True),
                      "gross_return": [0.002, -0.001]})
    s = score(t, 0.0005)
    assert s["avg_net_bp"] == pytest.approx(0.0)
    assert s["win_rate"] == pytest.approx(0.5)
