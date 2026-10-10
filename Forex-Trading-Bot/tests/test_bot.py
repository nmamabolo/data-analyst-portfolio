import numpy as np
import pandas as pd
import pytest

from forexbot.backtest import RiskSettings, quote_to_usd, run_backtest
from forexbot.data import PairSpec, load_fed_daily, load_ohlc_csv, pair_spec
from forexbot.indicators import atr
from forexbot.strategy import MACrossover

NO_COST = PairSpec("EURUSD", 0.0001, 0.0)
SMALL = MACrossover(fast=2, slow=4, atr_period=2, stop_atr=2.0, target_atr=0.0, trailing=False)


def make_bars(closes, start="2020-01-01"):
    close = pd.Series(closes, index=pd.bdate_range(start, periods=len(closes)), dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close),
                         "low": np.minimum(open_, close), "close": close})


def v_shape():
    """Falls, then rallies hard, forcing one upward crossover."""
    return make_bars([1.10, 1.09, 1.08, 1.07, 1.06, 1.05, 1.06, 1.08, 1.10, 1.12, 1.14, 1.16])


def test_atr_on_constant_range():
    bars = make_bars([1.0, 1.1] * 10)
    assert atr(bars.high, bars.low, bars.close, 3).iloc[-1] == pytest.approx(0.1)


def test_signal_fires_once_on_crossover():
    ind = SMALL.indicators(v_shape())
    assert list(ind.signal[ind.signal != 0]) == [1]


def test_entry_fills_at_next_bar_open():
    bars = v_shape()
    result = run_backtest(bars, NO_COST, SMALL)
    signal_day = result.indicators.index[result.indicators.signal == 1][0]
    entry_day = bars.index[bars.index.get_loc(signal_day) + 1]
    assert result.open_position.entry_date == entry_day
    assert result.open_position.entry_price == pytest.approx(bars.open[entry_day])


def test_no_lookahead_future_bars_do_not_change_past():
    bars = v_shape()
    full = run_backtest(bars, NO_COST, SMALL).equity
    cut = run_backtest(bars.iloc[:9], NO_COST, SMALL).equity
    pd.testing.assert_series_equal(full.iloc[:9], cut)


def test_position_size_risks_target_fraction():
    risk = RiskSettings(initial_equity=100_000, risk_pct=0.01, max_leverage=100)
    pos = run_backtest(v_shape(), NO_COST, SMALL, risk).open_position
    assert pos.risk_usd == pytest.approx(1_000, rel=0.02)
    assert pos.units % 1_000 == 0


def test_leverage_cap_limits_size():
    risk = RiskSettings(initial_equity=10_000, risk_pct=0.5, max_leverage=2)
    pos = run_backtest(v_shape(), NO_COST, SMALL, risk).open_position
    assert pos.units * pos.entry_price <= 2 * 10_000


def test_stop_fills_at_level_and_loses_one_r():
    bars = make_bars([1.10, 1.09, 1.08, 1.07, 1.06, 1.05, 1.06, 1.08, 1.10, 1.12, 1.00, 0.99])
    trades = run_backtest(bars, NO_COST, SMALL).trades
    stop_trade = trades.iloc[0]
    assert stop_trade.exit_reason == "stop"
    assert stop_trade.exit_price == pytest.approx(stop_trade.stop)
    assert stop_trade.r_multiple == pytest.approx(-1.0, abs=0.02)


def test_gap_through_stop_fills_at_open():
    bars = make_bars([1.10, 1.09, 1.08, 1.07, 1.06, 1.05, 1.06, 1.08, 1.10, 1.12, 1.12])
    bars.loc[bars.index[-1], ["open", "low"]] = 0.95  # weekend gap far below the stop
    trade = run_backtest(bars, NO_COST, SMALL).trades.iloc[0]
    assert trade.exit_price == pytest.approx(0.95)
    assert trade.r_multiple < -1


def test_spread_is_charged_on_both_sides():
    spec = PairSpec("EURUSD", 0.0001, 2.0)
    pos = run_backtest(v_shape(), spec, SMALL).open_position
    entry_day = pos.entry_date
    assert pos.entry_price == pytest.approx(v_shape().open[entry_day] + 0.0001)


def test_trailing_stop_only_tightens():
    strategy = MACrossover(fast=2, slow=4, atr_period=2, stop_atr=2.0, trailing=True)
    bars = v_shape()
    initial = run_backtest(bars.iloc[:9], NO_COST, strategy).open_position.stop
    later = run_backtest(bars, NO_COST, strategy).open_position.stop
    assert later > initial


def test_usd_base_pair_pnl_converts_from_quote_currency():
    spec = pair_spec("USDJPY")
    assert quote_to_usd(spec, 150.0) == pytest.approx(1 / 150)
    assert quote_to_usd(pair_spec("EURUSD"), 1.1) == 1.0
    with pytest.raises(ValueError):
        quote_to_usd(PairSpec("EURGBP", 0.0001, 1), 0.85)


def test_start_date_warms_up_indicators_without_trading_earlier():
    bars = load_fed_daily("EURUSD")
    result = run_backtest(bars, pair_spec("EURUSD"), MACrossover(), start="2019-01-01")
    assert result.equity.index[0] >= pd.Timestamp("2019-01-01")
    assert result.trades.entry_date.min() >= pd.Timestamp("2019-01-01")
    assert result.indicators.slow_ma.notna().all()


def test_bundled_data_is_market_convention():
    eur = load_fed_daily("EURUSD")
    assert 1.5 < eur.close["2008-07-15"] < 1.65   # EUR/USD all-time high area
    assert (eur.high >= eur.low).all()


def test_mt5_export_parses(tmp_path):
    path = tmp_path / "EURUSD_D1.csv"
    path.write_text("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n"
                    "2024.01.02\t00:00:00\t1.1040\t1.1045\t1.0940\t1.0943\t80000\n"
                    "2024.01.03\t00:00:00\t1.0943\t1.0960\t1.0892\t1.0920\t75000\n")
    bars = load_ohlc_csv(path)
    assert list(bars.columns) == ["open", "high", "low", "close"]
    assert bars.index[0] == pd.Timestamp("2024-01-02")
    assert bars.close.iloc[-1] == pytest.approx(1.0920)
