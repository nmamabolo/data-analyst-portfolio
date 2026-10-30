"""Gold RSI 80/20 lab: "sell at 80, buy at 20" on XAU/USD, as the trader runs it in MT5.

The trader's setup (M15 chart): RSI(14) on close with levels 80 / 20, sell when RSI
reaches 80, buy when it reaches 20, trading 0.01 lot (1 ounce: a $1 move in gold is
$1 of profit or loss). Their chart also shows a moving average on price, tested
here as an optional EMA(50) trend filter.

Data: 1-minute spot gold, 2020 - Oct 2026, from the public archive
github.com/parshant65-lang/Gold-XAUUSD-1m-2020-2025-Historical-Data (pinned commit).
Its monthly averages match an independent gold series to about 0.1%. Files up to
30 Sep 2025 are in broker server time (EET/EEST) and are converted to UTC. It has four
holes in 2025 (10-68 days, ~4 months in all); the data is split at any gap longer
than 4 days, indicators restart after it, and no trade is held across it.

Protocol (fixed before testing): 2020-2022 first test, 2023 onwards final test.
Entries fill at the next bar's open. If a bar touches both stop and target, the stop
counts first. Costs per round trip: $0.20 (low) or $0.40 (typical) per ounce of spread
and commission, plus overnight financing of 4% a year on the position's value.

  python -m gold_rsi.lab
"""
import subprocess
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

from rsi_ichimoku.lab import atr, crosses_down, crosses_up, rsi

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data_cache"
RESULTS = HERE / "results"
REPO = "https://github.com/parshant65-lang/gold-xauusd-1m-2020-2025-historical-data"
COMMIT = "ac7238e342aa7b02d975e7c3c9683adf42b00138"
SPLIT = "2023-01-01"
MAX_GAP = pd.Timedelta(days=4)
TIMEFRAMES = {"M5": "5min", "M15": "15min", "H1": "1h"}
COSTS = {"low_cost": 0.20, "typical_cost": 0.40}     # $ per ounce per round trip
FINANCING = 0.04                                      # per year, on the position's value
LOT_OUNCES = 1.0                                      # 0.01 lot of XAU/USD = 1 troy ounce


# ---------- data ----------

def fetch(dest: Path = CACHE / "gold_repo") -> Path:
    """Shallow, CSV-only checkout of the pinned commit (about 160 MB)."""
    if not (dest / "XAUUSD").exists():
        dest.mkdir(parents=True, exist_ok=True)
        run = lambda *a: subprocess.run(["git", "-C", str(dest), *a], check=True, capture_output=True)
        run("init", "-q")
        run("remote", "add", "origin", REPO)
        run("sparse-checkout", "set", "--no-cone", "/XAUUSD/**/*.csv")
        run("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", COMMIT)
        run("checkout", "-q", "FETCH_HEAD")
    return dest


SERVER_CLOCK_UNTIL = pd.Timestamp("2025-10-01")   # files before this use broker server time
SERVER_TZ = "Europe/Athens"                       # EET/EEST: UTC+2 winter, UTC+3 summer, EU DST


def to_utc(stamps: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The archive labels everything UTC, but files up to 30 Sep 2025 are in the broker's server
    clock (EET/EEST, so the daily break falls at 00:00 and US jobs data at 15:30). Later files
    are true UTC (break at 21:00/22:00, jobs data at 12:30/13:30). Convert the older part."""
    stamps = pd.DatetimeIndex(stamps)
    server = stamps < SERVER_CLOCK_UNTIL
    out = pd.Series(stamps.tz_localize("UTC"))
    out[server] = stamps[server].tz_localize(SERVER_TZ, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return pd.DatetimeIndex(out)


def load_m1(source: Path | None = None) -> pd.DataFrame:
    cached = CACHE / "xauusd_m1.parquet"
    if cached.exists():
        return pd.read_parquet(cached)
    root = Path(source) if source else fetch()
    files = sorted(root.glob("XAUUSD/1m/*/*/*.csv"))
    df = pd.concat([pd.read_csv(f, usecols=["timestamp", "open", "high", "low", "close"]) for f in files])
    df.index = to_utc(pd.to_datetime(df.pop("timestamp"), unit="ms"))
    df = df[df.index.notna()].sort_index()
    df = df[~df.index.duplicated()].astype(float)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cached)
    return df


def bars(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    """OHLC bars with a `segment` id that changes after every data hole longer than MAX_GAP."""
    b = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b["segment"] = (b.index.to_series().diff() > MAX_GAP).cumsum().to_numpy()
    return b


# ---------- rules ----------

ENTRIES = ("touch", "confirm")
EXITS = ("reverse", "rsi_50", "atr_2_2", "atr_2_4")
FILTERS = ("none", "ema50_trend")
THE_TRADERS_RULE = ("M15", "touch", "reverse", "none")


def signals(b: pd.DataFrame, entry: str, exit_: str, filt: str):
    """Per-segment indicators; returns entry/exit flags, stop and target distances (in $)."""
    parts = []
    for _, s in b.groupby("segment", sort=True):
        r = rsi(s.close, 14)
        a = atr(s, 14)
        ema = s.close.ewm(span=50, adjust=False, min_periods=50).mean()
        if entry == "touch":                  # act the moment RSI reaches the level
            buy, sell = crosses_down(r, 20), crosses_up(r, 80)
        else:                                 # wait for RSI to turn back out of the zone
            buy, sell = crosses_up(r, 20), crosses_down(r, 80)
        if filt == "ema50_trend":
            buy, sell = buy & (s.close > ema), sell & (s.close < ema)
        if exit_ == "reverse":                # hold until the opposite signal, then flip
            xl, xs, stop, target = sell, buy, 3 * a, 0 * a
        elif exit_ == "rsi_50":
            xl, xs, stop, target = r >= 50, r <= 50, 3 * a, 0 * a
        else:
            sl, tp = (2, 2) if exit_ == "atr_2_2" else (2, 4)
            none = pd.Series(False, s.index)
            xl, xs, stop, target = none, none, sl * a, tp * a
        last = pd.Series(False, s.index)
        last.iloc[-1] = True                  # flat at the end of every data segment
        parts.append(pd.DataFrame({"el": buy, "es": sell, "xl": xl | last, "xs": xs | last,
                                   "stop": stop, "target": target, "end": last}))
    p = pd.concat(parts).reindex(b.index)
    flags = [p[c].fillna(False).to_numpy(np.bool_) for c in ("el", "es", "xl", "xs", "end")]
    return (*flags, p.stop.fillna(0).to_numpy(), p.target.fillna(0).to_numpy())


@nb.njit(cache=True)
def _simulate(o, h, l, c, el, es, xl, xs, end, stop, target):
    n = len(o)
    ent = np.empty(n, np.int64); ext = np.empty(n, np.int64)
    side = np.empty(n, np.int8); pnl = np.empty(n, np.float64); why = np.empty(n, np.int8)
    k, pos, px, sl, tp = 0, 0, 0.0, 0.0, 0.0
    for t in range(1, n):
        if pos != 0 and end[t - 1]:                                   # data hole: closed at last close
            pnl[k] = pos * (c[t - 1] - px); ext[k] = t - 1; why[k] = 3; k += 1; pos = 0
        if pos != 0 and ((pos > 0 and xl[t - 1]) or (pos < 0 and xs[t - 1])):
            pnl[k] = pos * (o[t] - px); ext[k] = t; why[k] = 1; k += 1; pos = 0
        if pos != 0 and pos * (o[t] - sl) <= 0:                       # gap through the stop
            pnl[k] = pos * (o[t] - px); ext[k] = t; why[k] = 0; k += 1; pos = 0
        if pos != 0 and tp != 0.0 and pos * (o[t] - tp) >= 0:         # gap through the target
            pnl[k] = pos * (o[t] - px); ext[k] = t; why[k] = 2; k += 1; pos = 0
        if pos == 0 and not end[t - 1] and stop[t - 1] > 0 and (el[t - 1] or es[t - 1]):
            pos = 1 if el[t - 1] else -1
            px = o[t]; sl = px - pos * stop[t - 1]
            tp = px + pos * target[t - 1] if target[t - 1] > 0 else 0.0
            ent[k] = t; side[k] = pos
        if pos != 0:
            worst = l[t] if pos > 0 else h[t]
            best = h[t] if pos > 0 else l[t]
            if pos * (worst - sl) <= 0:
                pnl[k] = pos * (sl - px); ext[k] = t; why[k] = 0; k += 1; pos = 0
            elif tp != 0.0 and pos * (best - tp) >= 0:
                pnl[k] = pos * (tp - px); ext[k] = t; why[k] = 2; k += 1; pos = 0
    return ent[:k], ext[:k], side[:k], pnl[:k], why[:k]


REASONS = np.array(["stop", "signal", "target", "data_gap"])


def trades_for(b: pd.DataFrame, entry: str, exit_: str, filt: str) -> pd.DataFrame:
    el, es, xl, xs, end, stop, target = signals(b, entry, exit_, filt)
    o, h, l, c = (b[x].to_numpy(np.float64) for x in ("open", "high", "low", "close"))
    ent, ext, side, pnl, why = _simulate(o, h, l, c, el, es, xl, xs, end, stop, target)
    t = pd.DataFrame({"entry_time": b.index[ent], "exit_time": b.index[ext], "side": side,
                      "entry_price": o[ent], "gross_usd": pnl * LOT_OUNCES, "exit_reason": REASONS[why]})
    held_days = (t.exit_time - t.entry_time).dt.total_seconds() / 86_400
    t["financing_usd"] = FINANCING * t.entry_price * LOT_OUNCES * held_days / 365
    return t


def score(t: pd.DataFrame, cost: float) -> dict:
    if len(t) < 2:
        return dict(trades=len(t))
    net = t.gross_usd - cost * LOT_OUNCES - t.financing_usd
    monthly = net.groupby(t.exit_time.dt.tz_localize(None).dt.to_period("M")).sum()
    months = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
    monthly = monthly.reindex(months, fill_value=0.0)
    equity = net.cumsum()
    wins, losses = net[net > 0].sum(), -net[net <= 0].sum()
    return dict(trades=len(t), win_rate=(net > 0).mean(), avg_net_usd=net.mean(),
                avg_gross_usd=t.gross_usd.mean(), profit_factor=wins / losses if losses > 0 else np.inf,
                total_net_usd=net.sum(), avg_month_usd=monthly.mean(), worst_month_usd=monthly.min(),
                profitable_months=(monthly > 0).mean(),
                max_drawdown_usd=(equity - equity.cummax().clip(lower=0)).min())


def run():
    RESULTS.mkdir(exist_ok=True)
    m1 = load_m1()
    rows, kept = [], {}
    for tf, rule in TIMEFRAMES.items():
        b = bars(m1, rule)
        for entry in ENTRIES:
            for exit_ in EXITS:
                for filt in FILTERS:
                    t = trades_for(b, entry, exit_, filt)
                    if (tf, entry, exit_, filt) == THE_TRADERS_RULE:
                        kept["traders_rule"] = t
                    for period, part in (("2020-2022", t[t.entry_time < SPLIT]), ("2023-2026", t[t.entry_time >= SPLIT])):
                        for cost_name, cost in COSTS.items():
                            rows.append(dict(timeframe=tf, entry=entry, exit=exit_, filter=filt, period=period,
                                             cost=cost_name, **score(part, cost)))
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "all_results.csv", index=False, float_format="%.4f")
    kept["traders_rule"].to_csv(RESULTS / "traders_rule_trades.csv", index=False, float_format="%.4f")
    return table


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    t = run()
    print(f"{len(t) // 4} rule combinations tested")
