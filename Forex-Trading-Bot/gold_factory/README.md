# 🏭🥇 Gold-Only Strategy Factory

A trader wanted to focus on **gold (XAU/USD) only**. The factory therefore **generated 3,277 new rules for gold**. They were tested on 15-minute, 1-hour, 4-hour and daily charts built from 2.3 million 1-minute bars (Jan 2020 – Oct 2026). Each rule faced three separate periods plus a luck control.

## The verdict

- **Gold showed no timing edge beyond luck.** **33** rules passed both early tests on real prices, but **58** passed on *shuffled* prices, where any real pattern is destroyed and only luck and gold's rise remain.
- **Most survivors then weakened in the final test.** On 2025–26 their median Sharpe was 0.47, below simply holding gold (0.63, about +15% a year). Gold more than doubled over the period, so most rules that "worked" were long gold.
- **One pattern stands out: gold tends to rise in the evening, roughly 19:00–23:00 UTC (21:00–01:00 South African time).** But it only became profitable from 2023, and after realistic costs only from 2025.

## 1. How the rules were created and tested

- **Rule families:**
  - the factory's trend, momentum, breakout, mean-reversion and volatility-shock blocks, with random parameters, filters, long/short modes and holding limits;
  - calendar rules on the daily chart;
  - **a new time-of-day family**: hold gold long or short from a given UTC hour for 1, 2, 4 or 8 hours every weekday (384 rules).
- **Three periods:** discover **2020–22** and confirm **2023–24**, each needing net Sharpe ≥ 0.5, at least 10 trades, and at least 5% time in the market. Then a one-time **final test, 2025 – Oct 2026**.
- **Luck control:** the same rules on shuffled returns, keeping gold's overall rise but destroying any timing. **Benchmark:** holding gold.
- **Costs:** $0.40 per ounce per round trip, plus 4% a year financing.
- **Data fixes** (see [`gold_rsi/`](../gold_rsi/)):
  - the archive's 2020 – Sep 2025 timestamps were broker server time, converted to UTC;
  - four holes in 2025 (about 4 months in total) are respected: no position crosses one, and every rule restarts after it.
- **Look-ahead check:** 0 of 150 sampled rules can see the future.

## 2. What survived

| | Tested | Passed (real) | Passed (luck) |
|---|---|---|---|
| All rules | 3,277 | **33** | **58** |
| Daily chart | 847 | 17 | 11 |
| 4-hour chart | 682 | 9 | 44 |
| 1-hour + 15-minute | 1,748 | 7 | 3 |
| Time-of-day rules | 384 | 1 | 0 |

- **Survivors were mostly long gold** (21 of 33 long-only).
- **In the final test,** 11 of 33 beat holding gold on Sharpe. Most of those were in the market only 3–10% of the time and earned 1–5% a year.
- **The one strong survivor** was "long gold 20:00–24:00 UTC": Sharpe 0.51 → 1.28 → 2.13 across the three periods.

## 3. The evening pattern

![Time-of-day heatmap](results/time_of_day_heatmap.png)

Each cell is the Sharpe ratio of holding gold long for 4 hours a day starting at that UTC hour (factory costs).
- **Evening starts (19:00–22:00 UTC)** became strongly positive in 2023–24 and 2025–26, and that held across neighbouring hours and window lengths, so it isn't one lucky setting.
- **London and New York hours (12:00–17:00 UTC)** lost money in all three periods.
- **In 2020–22, the evening was flat** (−0.3 to +0.5).

**The rule in dollars**, buying at 20:00 UTC and selling at 00:00 every weekday at **0.01 lot**. Costs are $0.40 spread and commission plus **one full night's swap** (about 4% a year), because the window crosses the 21:00/22:00 UTC rollover when brokers charge it:

![Evening rule by year](results/evening_rule_by_year.png)

| 0.01 lot | 2020–22 | 2023–24 | 2025 – Oct 2026 |
|---|---|---|---|
| Total | **−$217** | **+$18** | **+$1,121** |
| Average month | −$6 | +$1 | **+$53** |
| Profitable months | 31% | 42% | 62% |
| Worst month | −$56 | −$16 | −$111 |
| Worst drawdown | −$277 | −$48 | −$269 |

Across all 1,296 trades it made +$0.71 per trade on average, with a 44% win rate.

**How to read this:**
- **The evening effect is real in the data, but young.** It made money only in 2025–26. That includes 2026, when the rule earned **+$796 while gold itself fell**, so it isn't simply gold's rise.
- **Before that it lost or broke even.** About five years of nothing and under two years of profit suggests a recent regime, not a permanent law. A plausible explanation is strong Asian buying while US markets close and Asia opens, but this study can't prove that.
- **On a R10,000 account (about $600) at 0.01 lot:**
  - 2025–26 averaged about **R880 a month**, but with a worst drawdown of about **R4,500** (45% of the account).
  - In 2020–22 the same rule lost about **R100 a month**.

## 4. Before using it

1. **Forward-test it on a demo account** for at least 2–3 months: buy 0.01 lot at 20:00 UTC (22:00 SAST) and close at 00:00 UTC (02:00 SAST) on weekdays.
2. **Check your broker's swap.** The cost model charges one full night of financing per trade. A swap-free account, or a broker with a smaller gold swap, would improve results.
3. **Never risk money you need for bills.** Even in its good period, the worst month lost $111 per 0.01 lot.

## Run it

```bash
python -m gold_factory.run      # 3,277 rules, real + shuffled (~5 min; gold data from gold_rsi.lab)
python -m gold_factory.report   # heatmap, evening-rule trades and yearly chart
python -m pytest tests/test_gold_factory.py
```

> ⚠️ Research project, not financial advice.
