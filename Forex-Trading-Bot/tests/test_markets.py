import pandas as pd
import pytest

from markets.lab import CACHE, MARKETS, cost_fraction, load


@pytest.mark.skipif(not (CACHE / "ejtrader").exists(), reason="ejtrader data not downloaded (python -m markets.lab)")
def test_ejtrader_prices_are_rescaled_to_real_quotes():
    eur, jpy, xau = (load(m).close.median() for m in ("EURUSD", "USDJPY", "XAUUSD"))
    assert 0.9 < eur < 1.6 and 70 < jpy < 160 and 1000 < xau < 2500


def test_costs_are_realistic_fractions_of_price():
    assert cost_fraction("EURUSD", 1.155) == pytest.approx(1.0e-4 / 1.155)       # 1 pip
    assert cost_fraction("USDJPY", 109.3) == pytest.approx(1.0e-2 / 109.3)       # 1 pip on a yen pair
    assert cost_fraction("S&P 500", 2500) == pytest.approx(0.5 / 2500)           # half an index point
    assert cost_fraction("BTCUSD (2019-26)", 30_000) == pytest.approx(0.003)


def test_every_market_is_classified_and_priced():
    for name, (source, spread, pip, financing) in MARKETS.items():
        assert source and 0 <= financing <= 0.05
        assert spread is not None or name in ("BTCUSD (2019-26)", "V75 (simulated)")
