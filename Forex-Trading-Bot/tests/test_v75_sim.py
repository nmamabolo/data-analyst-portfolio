import numpy as np

from v75_sim.lab import simulate_year


def test_simulated_v75_matches_derivs_description():
    b = simulate_year(np.random.default_rng(1))
    r = np.log(b.close).diff().dropna()
    assert len(b) == 365 * 96                                      # 24/7 M15 bars
    assert abs(r.std() * np.sqrt(len(b)) - 0.75) < 0.02            # 75% annual volatility
    assert abs(r.autocorr()) < 0.03                                 # no memory from bar to bar
    assert (b.high >= b[["open", "close"]].max(axis=1)).all() and (b.low <= b[["open", "close"]].min(axis=1)).all()
