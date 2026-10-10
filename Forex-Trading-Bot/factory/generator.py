"""Strategy factory: randomly assemble trading rules from building blocks.

A strategy is a small dict (a "spec"). `positions(spec, ...)` turns it into a
daily target position in [-1, 1] that is decided on the close of day t and
earns the return from t to t+1. Nothing may peek at day t+1.

Building blocks (14 signal families):
  trend:      ma_trend, ma_cross, tsmom, donchian, near_high
  reversal:   zscore_rev, rsi_rev, short_rev
  shocks:     vol_shock (follow or fade a big daily move), vix_spike (buy fear)
  regime:     vix_regime (risk-on when fear is falling)
  calendar:   weekday, turn_of_month
  cross-asset (handled in xs_positions): xs_momentum, xs_reversal
Modifiers: trend filter, volatility-regime filter, VIX filter, long-only /
short-only / long-short, and an optional maximum holding period.
"""
from itertools import product

import numpy as np
import pandas as pd

RNG_SEED = 2026

SINGLE_FAMILIES = {
    "ma_trend": dict(n=[10, 20, 50, 100, 150, 200]),
    "ma_cross": dict(fast=[5, 10, 20, 50], slow=[50, 100, 200]),
    "tsmom": dict(lookback=[5, 10, 21, 63, 126, 252]),
    "donchian": dict(n=[10, 20, 55, 100, 200]),
    "near_high": dict(n=[63, 126, 252], within=[0.02, 0.05, 0.10]),
    "zscore_rev": dict(n=[5, 10, 20, 50], k=[1.0, 1.5, 2.0, 2.5], exit=[0.0, 0.5]),
    "rsi_rev": dict(n=[2, 3, 5, 14], low=[5, 10, 20, 30]),
    "short_rev": dict(lookback=[1, 2, 3, 5]),
    "vol_shock": dict(k=[1.5, 2.0, 2.5, 3.0], hold=[1, 3, 5, 10], follow=[True, False]),
    "vix_spike": dict(n=[10, 20, 50], jump=[0.15, 0.25, 0.40], hold=[5, 10, 21]),
    "vix_regime": dict(n=[5, 10, 20, 50, 100]),
    "weekday": dict(day=[0, 1, 2, 3, 4]),
    "turn_of_month": dict(before=[1, 2, 3, 4], after=[1, 2, 3, 5]),
}
FILTERS = {"none": {}, "trend": dict(n=[50, 100, 200]), "vol_low": dict(n=[20, 63]),
           "vol_high": dict(n=[20, 63]), "vix_calm": dict(level=[15, 20, 25]), "vix_fear": dict(level=[20, 25, 30])}
DIRECTIONS = ["long_short", "long_only", "short_only"]
XS_FAMILIES = {
    "xs_momentum": dict(lookback=[21, 63, 126, 252], top=[1, 2, 3], rebalance=[5, 21]),
    "xs_reversal": dict(lookback=[1, 3, 5, 10], top=[1, 2, 3], rebalance=[1, 5]),
}


def _pick(rng, grid):
    return {k: v[rng.integers(len(v))] for k, v in grid.items()}


def random_specs(n_single: int, n_xs: int, seed: int = RNG_SEED) -> list[dict]:
    rng = np.random.default_rng(seed)
    specs, seen = [], set()
    families = list(SINGLE_FAMILIES)
    while len(specs) < n_single:
        fam = families[rng.integers(len(families))]
        params = _pick(rng, SINGLE_FAMILIES[fam])
        if fam == "ma_cross" and params["fast"] >= params["slow"]:
            continue
        filt = list(FILTERS)[rng.integers(len(FILTERS))]
        spec = dict(family=fam, params=params, filter=filt, filter_params=_pick(rng, FILTERS[filt]),
                    direction=DIRECTIONS[rng.integers(3)],
                    max_hold=[0, 0, 5, 10, 21][rng.integers(5)])
        key = repr(spec)
        if key not in seen:
            seen.add(key)
            specs.append(spec)
    # The cross-asset grid is small (96 designs), so test every combination rather than sample.
    xs = [dict(family=fam, params=dict(zip(grid, values)), filter="none", filter_params={},
               direction=direction, max_hold=0)
          for fam, grid in XS_FAMILIES.items()
          for values in product(*grid.values())
          for direction in DIRECTIONS[:2]]
    return specs + xs[:n_xs]


def describe(spec: dict) -> str:
    p = ", ".join(f"{k}={v}" for k, v in spec["params"].items())
    f = "" if spec["filter"] == "none" else f" | {spec['filter']}({', '.join(f'{k}={v}' for k, v in spec['filter_params'].items())})"
    h = f" | max {spec['max_hold']}d" if spec.get("max_hold") else ""
    return f"{spec['family']}({p}){f} | {spec['direction']}{h}"


# ---------- single-market signals ----------

def _hold_events(events: pd.Series, hold: int) -> pd.Series:
    """Turn +1/-1 event days into a position held for `hold` days (latest event wins)."""
    out = events.replace(0, np.nan)
    return out.ffill(limit=hold - 1).fillna(0) if hold > 1 else events.astype(float)


def _state(entries: pd.Series) -> pd.Series:
    """+1/-1 entries, 0 exits, NaN = keep previous state."""
    return entries.ffill().fillna(0)


def raw_signal(family: str, p: dict, close: pd.Series, vix: pd.Series) -> pd.Series:
    ret = close.pct_change()
    if family == "ma_trend":
        return np.sign(close - close.rolling(p["n"]).mean())
    if family == "ma_cross":
        return np.sign(close.rolling(p["fast"]).mean() - close.rolling(p["slow"]).mean())
    if family == "tsmom":
        return np.sign(close.pct_change(p["lookback"]))
    if family == "donchian":
        hi, lo = close.rolling(p["n"]).max(), close.rolling(p["n"]).min()
        return _state(pd.Series(np.where(close >= hi, 1.0, np.where(close <= lo, -1.0, np.nan)), close.index))
    if family == "near_high":
        hi, lo = close.rolling(p["n"]).max(), close.rolling(p["n"]).min()
        return pd.Series(np.where(close >= hi * (1 - p["within"]), 1.0,
                                  np.where(close <= lo * (1 + p["within"]), -1.0, 0.0)), close.index)
    if family == "zscore_rev":
        z = (close - close.rolling(p["n"]).mean()) / close.rolling(p["n"]).std()
        e = np.where(z < -p["k"], 1.0, np.where(z > p["k"], -1.0, np.where(z.abs() <= p["exit"], 0.0, np.nan)))
        return _state(pd.Series(e, close.index))
    if family == "rsi_rev":
        d = close.diff()
        up = d.clip(lower=0).ewm(alpha=1 / p["n"], adjust=False).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / p["n"], adjust=False).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        e = np.where(rsi < p["low"], 1.0, np.where(rsi > 100 - p["low"], -1.0, np.where(rsi.between(45, 55), 0.0, np.nan)))
        return _state(pd.Series(e, close.index))
    if family == "short_rev":
        return -np.sign(close.pct_change(p["lookback"]))
    if family == "vol_shock":
        sd = ret.rolling(20).std().shift(1)
        ev = np.sign(ret).where(ret.abs() > p["k"] * sd, 0.0)
        ev = ev if p["follow"] else -ev
        return _hold_events(ev, p["hold"])
    if family == "vix_spike":
        ev = (vix > vix.rolling(p["n"]).mean() * (1 + p["jump"])).astype(float)
        return _hold_events(ev, p["hold"])
    if family == "vix_regime":
        return np.sign(vix.rolling(p["n"]).mean() - vix)   # +1 when fear is below its average
    if family == "weekday":
        # Hold from close of the previous day through the close of `day`.
        next_day = (close.index + pd.offsets.BDay(1)).dayofweek   # calendar, not the next data row
        return pd.Series((next_day == p["day"]).astype(float), close.index)
    if family == "turn_of_month":
        # Uses the weekday calendar (known in advance), never the data's own future rows.
        nxt = (close.index + pd.offsets.BDay(1)).values.astype("datetime64[D]")
        month_start = nxt.astype("datetime64[M]").astype("datetime64[D]")
        month_end = (nxt.astype("datetime64[M]") + np.timedelta64(1, "M")).astype("datetime64[D]")
        nxt_pos = np.busday_count(month_start, nxt)          # business days before t+1 this month
        nxt_left = np.busday_count(nxt, month_end) - 1       # business days after t+1 this month
        return pd.Series(((nxt_left < p["before"]) | (nxt_pos < p["after"])).astype(float), close.index)
    raise ValueError(family)


def apply_filter(sig: pd.Series, name: str, p: dict, close: pd.Series, vix: pd.Series) -> pd.Series:
    if name == "none":
        return sig
    if name == "trend":
        t = np.sign(close - close.rolling(p["n"]).mean())
        return sig.where(np.sign(sig) == t, 0.0)
    if name in ("vol_low", "vol_high"):
        vol = close.pct_change().rolling(p["n"]).std()
        median = vol.rolling(504, min_periods=252).median()
        ok = vol < median if name == "vol_low" else vol > median
        return sig.where(ok, 0.0)
    if name == "vix_calm":
        return sig.where(vix < p["level"], 0.0)
    if name == "vix_fear":
        return sig.where(vix > p["level"], 0.0)
    raise ValueError(name)


def apply_direction(sig: pd.Series, direction: str) -> pd.Series:
    if direction == "long_only":
        return sig.clip(lower=0)
    if direction == "short_only":
        return sig.clip(upper=0)
    return sig


def apply_max_hold(pos: pd.Series, max_hold: int) -> pd.Series:
    """Flatten a position after `max_hold` days until the signal changes."""
    if not max_hold:
        return pos
    run_id = (pos != pos.shift()).cumsum()
    age = pos.groupby(run_id).cumcount()
    return pos.where(age < max_hold, 0.0)


def positions(spec: dict, close: pd.Series, vix: pd.Series) -> pd.Series:
    sig = raw_signal(spec["family"], spec["params"], close, vix)
    sig = apply_filter(sig, spec["filter"], spec["filter_params"], close, vix)
    sig = apply_direction(sig, spec["direction"])
    sig = apply_max_hold(sig.fillna(0.0), spec.get("max_hold", 0))
    return sig.where(close.notna(), 0.0).fillna(0.0)


# ---------- cross-asset signals ----------

def xs_positions(spec: dict, closes: pd.DataFrame) -> pd.DataFrame:
    """Rank markets by past return; long the top `top`, short the bottom `top` (long_short)."""
    p = spec["params"]
    past = closes.pct_change(p["lookback"])
    # Rank on volatility-adjusted past return so one wild market doesn't always top the list.
    vol = closes.pct_change().rolling(63).std() * np.sqrt(p["lookback"])
    score = past / vol
    if spec["family"] == "xs_reversal":
        score = -score
    rank = score.rank(axis=1, ascending=False)
    n = score.notna().sum(axis=1)
    longs = (rank <= p["top"]).astype(float)
    shorts = (rank > n.values[:, None] - p["top"]).astype(float) * (n.values[:, None] > 2 * p["top"])
    w = longs - (shorts if spec["direction"] == "long_short" else 0)
    w = w.where(score.notna(), 0.0)
    # Only rebalance every `rebalance` days.
    keep = np.arange(len(w)) % p["rebalance"] == 0
    w = w.where(pd.Series(keep, w.index), np.nan).ffill().fillna(0.0)
    gross = w.abs().sum(axis=1).replace(0, np.nan)
    return w.div(gross, axis=0).fillna(0.0)   # 100% gross exposure across the basket
