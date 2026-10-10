"""Performance statistics for an equity curve and its trade log."""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def summarize(equity: pd.Series, trades: pd.DataFrame) -> dict:
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = returns.mean() / returns.std() * np.sqrt(TRADING_DAYS) if returns.std() > 0 else np.nan
    max_dd = drawdown(equity).min()

    stats = {
        "start": equity.index[0].date(), "end": equity.index[-1].date(),
        "final_equity": equity.iloc[-1], "total_return": total_return, "cagr": cagr,
        "volatility": vol, "sharpe": sharpe, "max_drawdown": max_dd,
        "calmar": cagr / abs(max_dd) if max_dd < 0 else np.nan,
        "trades": len(trades),
    }
    if len(trades):
        wins, losses = trades.loc[trades.pnl_usd > 0, "pnl_usd"], trades.loc[trades.pnl_usd <= 0, "pnl_usd"]
        stats.update({
            "win_rate": len(wins) / len(trades),
            "avg_win_usd": wins.mean() if len(wins) else 0.0,
            "avg_loss_usd": losses.mean() if len(losses) else 0.0,
            "profit_factor": wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf,
            "expectancy_r": trades.r_multiple.mean(),
            "avg_bars_held": trades.bars_held.mean(),
        })
    return stats


def format_summary(stats: dict) -> pd.Series:
    """Human-readable version of `summarize` output for printing."""
    pct = {"total_return", "cagr", "volatility", "max_drawdown", "win_rate"}
    money = {"final_equity", "avg_win_usd", "avg_loss_usd"}
    out = {}
    for key, value in stats.items():
        if key == "trades":
            out[key] = f"{int(value):,}"
        elif key in pct:
            out[key] = f"{value:.1%}"
        elif key in money:
            out[key] = f"${value:,.0f}"
        elif isinstance(value, float):
            out[key] = f"{value:.2f}"
        else:
            out[key] = str(value)
    return pd.Series(out)
