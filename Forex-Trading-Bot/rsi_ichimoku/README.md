# 📉 RSI + Ichimoku: Testing a Trader's Own MT5 Setup

A trader shared their MetaTrader 5 indicator settings:

| Indicator | Their settings | Standard settings (tested alongside) |
|---|---|---|
| RSI | period 14 on close, levels **10 / 20 / 80 / 90** | levels 30 / 70 (and 20 / 80) |
| Ichimoku | **Tenkan 5, Kijun 2, Senkou B 52** | 9 / 26 / 52 |

Note that in their setup **Kijun (2) is faster than Tenkan (5)**. Normally Kijun is the slower line, so their Tenkan/Kijun crosses signal the opposite of the textbook cross.

## How it was tested

- **Markets:** EUR/USD (HistData 1-minute bars, 2019–2025) and Bitcoin (Bitstamp 1-minute bars, 2019 – Oct 2026), rebuilt into **M5, M15, H1, H4 and D1** charts.
- **Six common ways to trade these indicators**, all fixed before testing:

| Rule | Enter | Exit |
|---|---|---|
| RSI reversal | RSI crosses back up through the low level (buy) or down through the high level (sell) | RSI reaches 50 |
| RSI reversal, extreme levels | same, at 10 / 90 | RSI reaches 50 |
| RSI reversal, hold to opposite level | same entries | RSI reaches the opposite level |
| Ichimoku TK cross | Tenkan crosses Kijun, with price on the matching side of the cloud | opposite cross |
| Ichimoku cloud breakout | close breaks out of the cloud | close back through the Kijun |
| Cloud trend + RSI pullback | RSI bounce, only in the cloud's trend direction | RSI opposite level, or close through the cloud |

- **Realism:**
  - Indicators follow MT5's definitions; the cloud is shifted forward by the Kijun period, so it's known before each bar opens.
  - Fills happen at the next bar's open, and every trade has a protective stop of 3 × ATR(14). If a bar touches both stop and exit, the stop counts first.
  - Round-trip costs: EUR/USD 0.6 or 1.0 pip; Bitcoin 0.10% or 0.30%.
- **Two periods:** 2019–2022, then 2023 onwards as the final test.
- **Scope:** 2 markets × 5 timeframes × 2 settings × 6 rules = **120 combinations**.

## Results

| | Combinations with ≥ 20 trades in both periods | Profitable in both periods, before costs | after low costs | after typical costs |
|---|---|---|---|---|
| All | 82 | 25 | 10 | 7 |
| Trader's settings | 37 | | **3** | |
| Standard settings | 45 | | 7 | |

**About 25 of 82 is what pure luck would give.** With no edge at all, roughly a quarter of combinations (½ × ½) come out positive in both periods before costs, which is about 20. So most "winners" here are noise.

The two strongest results, at typical costs:

| | Trades (2019–22 / 2023–26) | Strategy return | Buy & hold | Worst drawdown |
|---|---|---|---|---|
| **Bitcoin D1, cloud breakout, standard 9/26/52** | 41 / 51 | +17.6% / +13.3% a year | **+44% / +53% a year** | −37% / −53% (holding: −77% / −53%) |
| **EUR/USD D1, TK cross, trader's 5/2/52** | 21 / 22 | +0.6% / +1.0% a year | −1.4% / +3.3% a year | −2% / −1% |

- **Bitcoin:** the cloud breakout made money, but far less than just holding Bitcoin. All the profit came from longs; shorts lost about 26–28% in each period.
- **EUR/USD:** the trader's settings give a small, steady edge on the daily chart, but only **about 1% a year**, from about 3 trades a year. On R10,000 that's roughly R8 a month.

**Everything else lost money.** The RSI reversals lose on every timeframe. The M5 and M15 versions trade often and pay costs on every trade. For Bitcoin, a 0.30% cost on every trade wipes out all the intraday rules. The "cloud trend + RSI pullback" combo almost never fires with these settings, because RSI rarely reaches 20 while price is above the cloud.

## Not tested yet

- **The trader's own entry and exit rules.** These six rules are common interpretations; the real ones may differ.
- **Long-only Bitcoin trend rules.** These are suggested by the losing shorts above, but choosing them now, after seeing the results, would need a fresh test period to be trustworthy.
- **Gold and indices.** Free intraday data wasn't available in this environment.

## Run it

```bash
python -m rsi_ichimoku.lab     # all 120 combinations -> results/all_results.csv (~30 s after the first data build)
python -m pytest tests/test_rsi_ichimoku.py
```

> ⚠️ Research project, not financial advice.
