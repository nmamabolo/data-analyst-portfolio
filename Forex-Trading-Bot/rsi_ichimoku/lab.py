"""RSI + Ichimoku lab: the user's own MetaTrader 5 settings, tested on real intraday data.

Settings under test (from the user's MT5 screens):
  RSI(14) on close, levels 10 / 20 / 80 / 90
  Ichimoku Tenkan 5, Kijun 2, Senkou Span B 52
Standard settings (RSI 30/70, Ichimoku 9/26/52) run alongside for comparison.

Markets: EUR/USD (HistData 1-minute, 2019-2025) and BTC/USD (Bitstamp 1-minute,
2019-2026), rebuilt into M5, M15, H1, H4 and D1 bars.

Protocol: every rule is fixed before testing. 2019-2022 is the first test,
2023 onwards the final test. Entries fill at the next bar's open, every trade
carries a protective stop of 3 x ATR(14) (stop wins if a bar touches both),
and a round-trip cost is charged on every trade.

  python -m rsi_ichimoku.lab
"""
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent / "results"
CACHE = Path(__file__).resolve().parent.parent / "factory" / "data_cache"
SPLIT = "2023-01-01"
TIMEFRAMES = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h", "D1": "1D"}
# Round-trip cost as a fraction of price: (low, typical)
COSTS = {"EURUSD": (0.6e-4 / 1.10, 1.0e-4 / 1.10), "BTCUSD": (0.0010, 0.0030)}
SETTINGS = {
    "yours": dict(rsi=14, low=20, high=80, low_x=10, high_x=90, tenkan=5, kijun=2, span_b=52),
    "standard": dict(rsi=14, low=30, high=70, low_x=20, high_x=80, tenkan=9, kijun=26, span_b=52),
}
STOP_ATR = 3.0


# ---------- data ----------

def eurusd_m1() -> pd.DataFrame:
    from scalping.data_m1 import load
    return load()[["open", "high", "low", "close"]]


def btcusd_m1(start="2019-01-01") -> pd.DataFrame:
    cached = CACHE / "btc_m1_2019.parquet"
    if cached.exists():
        return pd.read_parquet(cached)
    from factory.data import _download
    parts = []
    for key in ("btc_hist", "btc_new"):
        for chunk in pd.read_csv(_download(key), chunksize=2_000_000,
                                 usecols=["timestamp", "open", "high", "low", "close"]):
            chunk.index = pd.to_datetime(chunk.pop("timestamp"), unit="s", utc=True)
            parts.append(chunk.loc[start:])
    df = pd.concat(parts).sort_index()
    df = df[~df.index.duplicated(keep="last")].astype(float)
    df.to_parquet(cached)
    return df


def bars(m1: pd.DataFrame, rule: str, market: str) -> pd.DataFrame:
    # FX trading days roll at 22:00 UTC (17:00 New York); crypto days at midnight UTC.
    if market == "EURUSD" and rule == "1D":
        rule, offset = "24h", "22h"      # a fixed 24h rule, because pandas ignores offset for "1D"
    else:
        offset = None
    out = m1.resample(rule, offset=offset, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return out[out.high > out.low] if offset else out


# ---------- indicators (MetaTrader 5 definitions) ----------

def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def atr(b: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = b.close.shift(1)
    tr = pd.concat([b.high - b.low, (b.high - prev).abs(), (b.low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ichimoku(b: pd.DataFrame, tenkan: int, kijun: int, span_b: int) -> pd.DataFrame:
    """MT5 iIchimoku: both Senkou spans are plotted `kijun` bars ahead, so the cloud
    under bar t was computed at bar t - kijun and is known before t opens."""
    mid = lambda n: (b.high.rolling(n).max() + b.low.rolling(n).min()) / 2
    t, k = mid(tenkan), mid(kijun)
    a = ((t + k) / 2).shift(kijun)
    bb = mid(span_b).shift(kijun)
    return pd.DataFrame({"tenkan": t, "kijun": k, "cloud_top": np.maximum(a, bb),
                         "cloud_bottom": np.minimum(a, bb)})


# ---------- rules ----------

def crosses_up(x: pd.Series, level) -> pd.Series:
    return (x > level) & (x.shift(1) <= (level.shift(1) if isinstance(level, pd.Series) else level))


def crosses_down(x: pd.Series, level) -> pd.Series:
    return (x < level) & (x.shift(1) >= (level.shift(1) if isinstance(level, pd.Series) else level))


def rules(b: pd.DataFrame, s: dict) -> dict:
    """Each rule: (enter_long, enter_short, exit_long, exit_short), decided on the close."""
    r = rsi(b.close, s["rsi"])
    ich = ichimoku(b, s["tenkan"], s["kijun"], s["span_b"])
    above = b.close > ich.cloud_top
    below = b.close < ich.cloud_bottom
    tk_up, tk_dn = crosses_up(ich.tenkan, ich.kijun), crosses_down(ich.tenkan, ich.kijun)
    lo, hi, lox, hix = s["low"], s["high"], s["low_x"], s["high_x"]
    out = {
        # RSI bounces back out of oversold / overbought; exit when RSI reaches 50
        f"RSI reversal {lo}/{hi}, exit 50": (crosses_up(r, lo), crosses_down(r, hi), r >= 50, r <= 50),
        f"RSI reversal {lox}/{hix}, exit 50": (crosses_up(r, lox), crosses_down(r, hix), r >= 50, r <= 50),
        # Same entries, held until the opposite extreme
        f"RSI reversal {lo}/{hi}, exit opposite level": (crosses_up(r, lo), crosses_down(r, hi), r >= hi, r <= lo),
        # Ichimoku trend: Tenkan/Kijun cross on the right side of the cloud
        "Ichimoku TK cross with cloud": (tk_up & above, tk_dn & below, tk_dn, tk_up),
        # Ichimoku breakout: close breaks out of the cloud; exit on a close back through the Kijun
        "Ichimoku cloud breakout": (crosses_up(b.close, ich.cloud_top), crosses_down(b.close, ich.cloud_bottom),
                                    b.close < ich.kijun, b.close > ich.kijun),
        # Combo: trade RSI pullbacks only in the direction of the cloud trend
        f"Cloud trend + RSI {lo}/{hi} pullback": (above & crosses_up(r, lo), below & crosses_down(r, hi),
                                                  (r >= hi) | below, (r <= lo) | above),
    }
    return {k: tuple(np.asarray(x.fillna(False), dtype=np.bool_) for x in v) for k, v in out.items()}


# ---------- simulator ----------

@nb.njit(cache=True)
def _simulate(o, h, l, c, el, es, xl, xs, stop):
    n = len(o)
    ent = np.empty(n, np.int64)
    ext = np.empty(n, np.int64)
    side = np.empty(n, np.int8)
    ret = np.empty(n, np.float64)
    why = np.empty(n, np.int8)        # 0 stop, 1 signal
    k, pos, px, sl, t0 = 0, 0, 0.0, 0.0, 0
    for t in range(1, n):
        # At the open: act on yesterday's exit signal, then on a new entry
        if pos != 0 and ((pos > 0 and xl[t - 1]) or (pos < 0 and xs[t - 1])):
            ret[k] = pos * (o[t] / px - 1); ext[k] = t; why[k] = 1; k += 1; pos = 0
        if pos != 0 and pos * (o[t] - sl) <= 0:          # gap through the stop
            ret[k] = pos * (o[t] / px - 1); ext[k] = t; why[k] = 0; k += 1; pos = 0
        if pos == 0 and stop[t - 1] > 0 and (el[t - 1] or es[t - 1]):
            pos = 1 if el[t - 1] else -1
            px = o[t]; sl = px - pos * stop[t - 1]; t0 = t
            ent[k] = t; side[k] = pos
        # During the bar: protective stop
        if pos != 0:
            worst = l[t] if pos > 0 else h[t]
            if pos * (worst - sl) <= 0:
                ret[k] = pos * (sl / px - 1); ext[k] = t; why[k] = 0; k += 1; pos = 0
    return ent[:k], ext[:k], side[:k], ret[:k], why[:k]


def simulate(b: pd.DataFrame, signals: tuple, stop: np.ndarray) -> pd.DataFrame:
    o, h, l, c = (b[x].to_numpy(np.float64) for x in ("open", "high", "low", "close"))
    ent, ext, side, ret, why = _simulate(o, h, l, c, *signals, np.nan_to_num(stop))
    return pd.DataFrame({"entry_time": b.index[ent], "exit_time": b.index[ext], "side": side,
                         "gross_return": ret, "bars_held": ext - ent,
                         "exit_reason": np.where(why == 0, "stop", "signal")})


def score(trades: pd.DataFrame, cost: float) -> dict:
    if len(trades) < 2:
        return dict(trades=len(trades))
    net = trades.gross_return - cost
    daily = net.groupby(trades.exit_time.dt.floor("D")).sum()
    days = pd.date_range(trades.entry_time.min().floor("D"), trades.exit_time.max().floor("D"), freq="D")
    daily = daily.reindex(days, fill_value=0.0)
    wins, losses = net[net > 0].sum(), -net[net <= 0].sum()
    growth = np.log1p(net.clip(lower=-0.99)).sum()   # trading the full account on every trade, no leverage
    years = max((days[-1] - days[0]).days / 365.25, 1 / 12)
    return dict(trades=len(trades), trades_per_week=len(trades) / years / 52,
                win_rate=(net > 0).mean(), avg_net_bp=net.mean() * 1e4, avg_gross_bp=trades.gross_return.mean() * 1e4,
                profit_factor=wins / losses if losses > 0 else np.inf,
                sharpe=daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else np.nan,
                annual_return_1x=np.expm1(growth / years))


def run():
    RESULTS.mkdir(exist_ok=True)
    rows = []
    for market, loader in (("EURUSD", eurusd_m1), ("BTCUSD", btcusd_m1)):
        m1 = loader()
        print(f"{market}: {len(m1):,} one-minute bars, {m1.index[0].date()} to {m1.index[-1].date()}")
        for tf, rule in TIMEFRAMES.items():
            b = bars(m1, rule, market)
            stop = (STOP_ATR * atr(b)).to_numpy()
            for set_name, s in SETTINGS.items():
                for name, sig in rules(b, s).items():
                    trades = simulate(b, sig, stop)
                    for period, part in (("2019-2022", trades[trades.entry_time < SPLIT]),
                                         ("2023-2026", trades[trades.entry_time >= SPLIT])):
                        for cost_name, cost in zip(("low_cost", "typical_cost"), COSTS[market]):
                            rows.append(dict(market=market, timeframe=tf, settings=set_name, rule=name,
                                             period=period, cost=cost_name, **score(part, cost)))
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "all_results.csv", index=False, float_format="%.5f")
    return table


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    t = run()
    print(f"{len(t) // 4} market x timeframe x setting x rule combinations tested")
