"""Fast intraday trade simulator (numba) shared by every scalping strategy.

A strategy supplies, for each bar t (known at the close of t):
  signal[t]   +1 buy, -1 sell, 0 nothing
  stop[t]     stop distance in price units
  target[t]   target distance in price units (0 = no target)
  flat[t]     True if no position may be held during bar t (session end)

Fill rules, chosen to be pessimistic:
  * entry at the open of bar t+1
  * a gap through the stop fills at the open
  * if one bar touches both stop and target, the stop is taken
  * positions still open after `max_hold` bars exit at that bar's close
  * when `flat` turns on, any position is closed at that bar's open
Costs (spread + commission + slippage, in pips) are subtracted per round trip
after the fact so one simulation can be priced at several cost levels.
"""
import numba as nb
import numpy as np
import pandas as pd

from .data_m1 import PIP


@nb.njit(cache=True)
def _simulate(o, h, l, c, signal, stop, target, flat, max_hold):
    n = len(o)
    entry_i = np.empty(n, np.int64)
    exit_i = np.empty(n, np.int64)
    direction = np.empty(n, np.int8)
    gross = np.empty(n, np.float64)
    risk = np.empty(n, np.float64)
    reason = np.empty(n, np.int8)  # 0 stop, 1 target, 2 time, 3 session
    k = 0
    pos = 0
    ent_px = 0.0
    sl = 0.0
    tp = 0.0
    ent = 0
    for t in range(1, n):
        # Open of bar t: session close or gap through stop
        if pos != 0:
            if flat[t]:
                gross[k] = pos * (o[t] - ent_px); exit_i[k] = t; reason[k] = 3; k += 1; pos = 0
            elif pos * (o[t] - sl) <= 0:
                gross[k] = pos * (o[t] - ent_px); exit_i[k] = t; reason[k] = 0; k += 1; pos = 0
        # New entry from the previous bar's signal
        if pos == 0 and signal[t - 1] != 0 and not flat[t] and stop[t - 1] > 0:
            pos = signal[t - 1]
            ent_px = o[t]
            sl = ent_px - pos * stop[t - 1]
            tp = ent_px + pos * target[t - 1] if target[t - 1] > 0 else 0.0
            ent = t
            entry_i[k] = t; direction[k] = pos; risk[k] = stop[t - 1]
        # During bar t: stop first, then target, then time stop
        if pos != 0:
            worst = l[t] if pos > 0 else h[t]
            best = h[t] if pos > 0 else l[t]
            if pos * (worst - sl) <= 0:
                gross[k] = pos * (sl - ent_px); exit_i[k] = t; reason[k] = 0; k += 1; pos = 0
            elif tp != 0.0 and pos * (best - tp) >= 0:
                gross[k] = pos * (tp - ent_px); exit_i[k] = t; reason[k] = 1; k += 1; pos = 0
            elif t - ent >= max_hold:
                gross[k] = pos * (c[t] - ent_px); exit_i[k] = t; reason[k] = 2; k += 1; pos = 0
    return entry_i[:k], exit_i[:k], direction[:k], gross[:k], risk[:k], reason[:k]


REASONS = np.array(["stop", "target", "time", "session"])


def simulate(bars: pd.DataFrame, signal, stop, target, flat, max_hold: int = 10_000) -> pd.DataFrame:
    """Run the simulator and return one row per trade (gross of costs)."""
    arrays = [bars[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")]
    out = _simulate(*arrays,
                    np.asarray(signal, np.int8),
                    np.nan_to_num(np.asarray(stop, np.float64)),
                    np.nan_to_num(np.asarray(target, np.float64)),
                    np.asarray(flat, np.bool_), max_hold)
    entry_i, exit_i, direction, gross, risk, reason = out
    return pd.DataFrame({
        "entry_time": bars.index[entry_i], "exit_time": bars.index[exit_i],
        "direction": direction, "gross_pips": gross / PIP, "risk_pips": risk / PIP,
        "bars_held": exit_i - entry_i, "exit_reason": REASONS[reason],
    })


def score(trades: pd.DataFrame, cost_pips: float) -> dict:
    """Net performance of a trade list at a given round-trip cost."""
    if trades.empty:
        return {"trades": 0, "net_pips_per_trade": np.nan, "gross_pips_per_trade": np.nan,
                "win_rate": np.nan, "profit_factor": np.nan, "net_r_per_trade": np.nan,
                "trades_per_day": 0.0, "total_net_pips": 0.0}
    net = trades.gross_pips - cost_pips
    days = max((trades.entry_time.iloc[-1] - trades.entry_time.iloc[0]).days * 5 / 7, 1)
    losses = -net[net <= 0].sum()
    return {
        "trades": len(trades),
        "trades_per_day": len(trades) / days,
        "gross_pips_per_trade": trades.gross_pips.mean(),
        "net_pips_per_trade": net.mean(),
        "win_rate": (net > 0).mean(),
        "profit_factor": net[net > 0].sum() / losses if losses > 0 else np.inf,
        "net_r_per_trade": (net / trades.risk_pips).mean(),
        "total_net_pips": net.sum(),
    }
