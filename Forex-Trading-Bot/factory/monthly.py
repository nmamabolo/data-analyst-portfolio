"""Monthly layer: S&P 500 and gold timing/rotation rules, same three-stage protocol.

The source prices are monthly averages, which makes month-to-month returns
artificially smooth (consecutive averages overlap). Every signal is therefore
lagged an extra month: data through month t decides the position for month t+2.
Cash earns 0% (conservative: real T-bills paid 0-5%).
"""
from itertools import product

import numpy as np
import pandas as pd

from .data import MONTHLY_COSTS, monthly_returns

SPLITS = {"discover": ("1972-01-01", "2008-12-31"), "confirm": ("2009-01-01", "2020-12-31"),
          "final": ("2021-01-01", None)}
LAG = 2
MONTHS = 12


def specs():
    out = [dict(rule="hold", asset=a) for a in ("SP500", "GOLD")]
    out += [dict(rule="mix", sp=w) for w in (0.5, 0.7)]
    for a, n in product(("SP500", "GOLD", "BOTH"), (3, 6, 8, 10, 12)):
        out.append(dict(rule="trend", asset=a, n=n))
    for a, n in product(("SP500", "GOLD", "BOTH"), (3, 6, 9, 12)):
        out.append(dict(rule="momentum", asset=a, n=n))
    out += [dict(rule="rotate", n=n) for n in (3, 6, 9, 12)]
    return out


def describe(s):
    return ", ".join(f"{k}={v}" for k, v in s.items())


def weights(spec, rets: pd.DataFrame) -> pd.DataFrame:
    """Target weights decided with data through each month (before the extra lag)."""
    index = (1 + rets.fillna(0)).cumprod()
    w = pd.DataFrame(0.0, index=rets.index, columns=rets.columns)
    rule = spec["rule"]
    if rule == "hold":
        w[spec["asset"]] = 1.0
    elif rule == "mix":
        w["SP500"], w["GOLD"] = spec["sp"], 1 - spec["sp"]
    elif rule in ("trend", "momentum"):
        n = spec["n"]
        on = index > index.rolling(n).mean() if rule == "trend" else index.pct_change(n) > 0
        assets = ["SP500", "GOLD"] if spec["asset"] == "BOTH" else [spec["asset"]]
        for a in assets:
            w[a] = on[a].astype(float) / len(assets)
    elif rule == "rotate":
        past = index.pct_change(spec["n"])
        best = past.fillna(-np.inf).idxmax(axis=1)
        for a in rets:
            w[a] = ((best == a) & (past[a] > 0)).astype(float)
    return w


def strategy_returns(spec, rets: pd.DataFrame) -> pd.Series:
    held = weights(spec, rets).shift(LAG).fillna(0.0)
    turnover = held.diff().abs().fillna(held.abs())
    tc = pd.Series({a: MONTHLY_COSTS[a][0] for a in rets})
    hc = pd.Series({a: MONTHLY_COSTS[a][1] for a in rets})
    return ((held * rets.fillna(0)).sum(axis=1) - (turnover * tc).sum(axis=1)
            - (held * hc).sum(axis=1) / MONTHS)


def stats(r: pd.Series) -> dict:
    out = {}
    for name, (a, b) in SPLITS.items():
        x = r.loc[a:b]
        out[f"{name}_sharpe"] = x.mean() / x.std() * np.sqrt(MONTHS) if x.std() > 0 else np.nan
        out[f"{name}_ann_return"] = (1 + x).prod() ** (MONTHS / len(x)) - 1
        dd = (1 + x).cumprod()
        out[f"{name}_max_dd"] = (dd / dd.cummax() - 1).min()
    return out


def evaluate():
    rets = monthly_returns()
    rows = []
    for i, s in enumerate(specs()):
        rows.append({"id": i, "spec": describe(s), **stats(strategy_returns(s, rets))})
    return pd.DataFrame(rows)


def passes(t: pd.DataFrame, min_sharpe=0.5) -> pd.DataFrame:
    return t[(t.discover_sharpe >= min_sharpe) & (t.confirm_sharpe >= min_sharpe)]
