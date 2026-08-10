# 🗄️ SQL Analytics — BPO Contact-Centre Database

A hands-on SQL project analysing a synthetic **BPO / call-centre** database with SQLite. It demonstrates joins, aggregation, `CASE` logic, `HAVING`, CTEs and **window functions** (`RANK`, `LAG`, `AVG/SUM OVER`, partitions) against realistic operational questions.

> All data is synthetic sample data — no real people or clients.

## 📦 Files

| File | Purpose |
|---|---|
| [`schema.sql`](./schema.sql) | Table definitions (campaigns, agents, calls) |
| [`queries.sql`](./queries.sql) | The full analytical query library |
| [`bpo_analytics.db`](./bpo_analytics.db) | Ready-to-run SQLite database |
| [`build_database.py`](./build_database.py) | Rebuilds the database from scratch |

## ▶️ Run it yourself

```bash
# open the prebuilt database
sqlite3 bpo_analytics.db
# ...or rebuild from scratch
python build_database.py
```

## 🧱 Data model

```
campaigns (campaign_id PK)
     │
     ├──< agents (agent_id PK, campaign_id FK)
     │         │
     └──< calls (call_id PK, campaign_id FK, agent_id FK)
```

**Scale:** 10 campaigns · 127 agents · 48,178 calls (Jun–Jul 2026).

---

## 📊 Query library & sample results

### 1. Campaign performance summary

*Volume, AHT, answer rate, CSAT and revenue per campaign*

```sql
SELECT
    c.campaign_name,
    c.campaign_type,
    COUNT(*)                                             AS total_calls,
    SUM(cl.answered)                                     AS answered,
    ROUND(100.0 * SUM(cl.answered) / COUNT(*), 1)        AS answer_rate_pct,
    ROUND(AVG(CASE WHEN cl.answered = 1 THEN cl.handle_time_sec END), 0) AS avg_aht_sec,
    ROUND(AVG(cl.csat), 2)                               AS avg_csat,
    ROUND(SUM(cl.sale_amount), 0)                        AS revenue
FROM calls cl
JOIN campaigns c ON c.campaign_id = cl.campaign_id
GROUP BY c.campaign_name, c.campaign_type
ORDER BY total_calls DESC;
```

**Sample output:**

| campaign_name | campaign_type | total_calls | answered | answer_rate_pct | avg_aht_sec | avg_csat | revenue |
|---|---|---|---|---|---|---|---|
| ABSA Collections | Collections | 7,030 | 6,510 | 92.6 | 318 | 3.57 | 0 |
| DStv Upsell | Sales | 6,167 | 5,725 | 92.8 | 320 | 3.58 | 785,124 |
| Takealot Care | Customer Care | 5,834 | 5,469 | 93.7 | 318 | 3.58 | 0 |
| Telkom Tech Support | Tech Support | 5,334 | 4,976 | 93.3 | 320 | 3.62 | 0 |
| MTN Retentions | Retentions | 4,675 | 4,367 | 93.4 | 318 | 3.62 | 543,564 |
| Vodacom Upgrades | Sales | 4,400 | 4,115 | 93.5 | 318 | 3.58 | 515,786 |
| Discovery Lead Gen | Lead Gen | 4,001 | 3,717 | 92.9 | 325 | 3.57 | 463,890 |
| Nedbank Debt Review | Collections | 3,885 | 3,619 | 93.2 | 319 | 3.58 | 0 |

### 2. Daily service level

*% of calls answered within 20s SLA, by day (last 14 days)*

```sql
WITH daily AS (
    SELECT
        call_date,
        COUNT(*)                                                        AS offered,
        SUM(CASE WHEN answered = 1 AND wait_time_sec <= 20 THEN 1 END)  AS within_sla,
        SUM(answered)                                                   AS answered,
        SUM(CASE WHEN answered = 0 THEN 1 END)                          AS abandoned
    FROM calls
    GROUP BY call_date
)
SELECT
    call_date,
    offered,
    ROUND(100.0 * within_sla / offered, 1) AS service_level_pct,
    ROUND(100.0 * abandoned  / offered, 1) AS abandon_rate_pct
FROM daily
ORDER BY call_date DESC
LIMIT 14;
```

**Sample output:**

| call_date | offered | service_level_pct | abandon_rate_pct |
|---|---|---|---|
| 2026-07-31 | 880 | 30.7 | 5.9 |
| 2026-07-30 | 957 | 34.8 | 6.6 |
| 2026-07-29 | 907 | 32.1 | 6.9 |
| 2026-07-28 | 936 | 28.3 | 5.8 |
| 2026-07-27 | 882 | 32.3 | 7.5 |
| 2026-07-26 | 479 | 30.9 | 9.4 |
| 2026-07-25 | 471 | 30.6 | 8.1 |
| 2026-07-24 | 870 | 31.4 | 5.6 |

### 3. Top 10 agents by volume

*Ranked leaderboard using a window function*

```sql
SELECT
    RANK() OVER (ORDER BY COUNT(*) DESC)          AS rank,
    a.full_name,
    c.campaign_name,
    COUNT(*)                                      AS calls_handled,
    ROUND(AVG(cl.handle_time_sec), 0)             AS avg_aht_sec,
    ROUND(AVG(cl.csat), 2)                        AS avg_csat
FROM calls cl
JOIN agents    a ON a.agent_id    = cl.agent_id
JOIN campaigns c ON c.campaign_id = cl.campaign_id
WHERE cl.answered = 1
GROUP BY a.agent_id, a.full_name, c.campaign_name
ORDER BY calls_handled DESC
LIMIT 10;
```

**Sample output:**

| rank | full_name | campaign_name | calls_handled | avg_aht_sec | avg_csat |
|---|---|---|---|---|---|
| 1 | Andile Khumalo | ABSA Collections | 470 | 328 | 3.54 |
| 2 | Sibusiso Khumalo | Takealot Care | 469 | 314 | 3.61 |
| 3 | Nonhlanhla Molefe | MTN Retentions | 464 | 309 | 3.59 |
| 4 | Amahle Naidoo | ABSA Collections | 463 | 319 | 3.71 |
| 5 | Dineo Mahlangu | MTN Retentions | 454 | 325 | 3.63 |
| 5 | Gift Mokoena | OUTsurance Sales | 454 | 311 | 3.65 |
| 7 | Keabetswe Pillay | MTN Retentions | 453 | 316 | 3.74 |
| 7 | Tshepo Mabaso | MTN Retentions | 453 | 316 | 3.61 |

### 4. Agent CSAT vs campaign average

*Each agent measured against their own campaign benchmark*

```sql
WITH agent_csat AS (
    SELECT
        a.agent_id,
        a.full_name,
        a.campaign_id,
        ROUND(AVG(cl.csat), 2) AS agent_csat,
        COUNT(cl.csat)         AS surveys
    FROM agents a
    JOIN calls  cl ON cl.agent_id = a.agent_id
    WHERE cl.csat IS NOT NULL
    GROUP BY a.agent_id, a.full_name, a.campaign_id
    HAVING COUNT(cl.csat) >= 20
)
SELECT
    full_name,
    agent_csat,
    ROUND(AVG(agent_csat) OVER (PARTITION BY campaign_id), 2)          AS campaign_avg_csat,
    ROUND(agent_csat - AVG(agent_csat) OVER (PARTITION BY campaign_id), 2) AS vs_campaign,
    CASE WHEN agent_csat < AVG(agent_csat) OVER (PARTITION BY campaign_id)
         THEN 'Below benchmark' ELSE 'At / above' END                 AS flag
FROM agent_csat
ORDER BY vs_campaign ASC
LIMIT 12;
```

**Sample output:**

| full_name | agent_csat | campaign_avg_csat | vs_campaign | flag |
|---|---|---|---|---|
| Sanele Buthelezi | 3.4 | 3.56 | -0.16 | Below benchmark |
| Kabelo Mahlangu | 3.46 | 3.62 | -0.16 | Below benchmark |
| Sipho Buthelezi | 3.42 | 3.58 | -0.16 | Below benchmark |
| Themba Molefe | 3.44 | 3.58 | -0.14 | Below benchmark |
| Neo Tshabalala | 3.44 | 3.58 | -0.14 | Below benchmark |
| Portia Ngcobo | 3.44 | 3.58 | -0.14 | Below benchmark |
| Zodwa Pillay | 3.45 | 3.58 | -0.13 | Below benchmark |
| Rethabile Molefe | 3.46 | 3.58 | -0.13 | Below benchmark |

### 5. Attrition by campaign

*Headcount, resignations and attrition rate*

```sql
SELECT
    c.campaign_name,
    COUNT(*)                                                  AS headcount,
    SUM(CASE WHEN a.status = 'Resigned' THEN 1 ELSE 0 END)    AS resigned,
    ROUND(100.0 * SUM(CASE WHEN a.status = 'Resigned' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_pct
FROM agents a
JOIN campaigns c ON c.campaign_id = a.campaign_id
GROUP BY c.campaign_name
ORDER BY attrition_pct DESC;
```

**Sample output:**

| campaign_name | headcount | resigned | attrition_pct |
|---|---|---|---|
| MTN Retentions | 16 | 6 | 37.5 |
| OUTsurance Sales | 11 | 4 | 36.4 |
| Standard Bank Helpdesk | 10 | 2 | 20 |
| Discovery Lead Gen | 11 | 2 | 18.2 |
| Telkom Tech Support | 14 | 2 | 14.3 |
| DStv Upsell | 16 | 2 | 12.5 |
| Nedbank Debt Review | 10 | 1 | 10 |
| Takealot Care | 14 | 1 | 7.1 |

### 6. Tenure cohort analysis

*Staff grouped into 0-3 / 3-6 / 6-12 / 12+ month bands*

```sql
WITH tenure AS (
    SELECT
        agent_id,
        status,
        CAST((julianday(COALESCE(exit_date, DATE('now'))) - julianday(hire_date)) / 30.44 AS INT) AS tenure_months
    FROM agents
)
SELECT
    CASE
        WHEN tenure_months < 3  THEN '0-3 months'
        WHEN tenure_months < 6  THEN '3-6 months'
        WHEN tenure_months < 12 THEN '6-12 months'
        ELSE '12+ months'
    END                                                          AS cohort,
    COUNT(*)                                                     AS headcount,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)           AS pct_of_staff,
    SUM(CASE WHEN status = 'Resigned' THEN 1 ELSE 0 END)         AS resigned,
    ROUND(100.0 * SUM(CASE WHEN status = 'Resigned' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_in_cohort_pct
FROM tenure
GROUP BY cohort
ORDER BY MIN(tenure_months);
```

**Sample output:**

| cohort | headcount | pct_of_staff | resigned | attrition_in_cohort_pct |
|---|---|---|---|---|
| 0-3 months | 5 | 3.9 | 4 | 80 |
| 3-6 months | 8 | 6.3 | 4 | 50 |
| 6-12 months | 28 | 22 | 5 | 17.9 |
| 12+ months | 86 | 67.7 | 7 | 8.1 |

### 7. Month-over-month volume

*Call volume with previous month and growth % via LAG*

```sql
WITH monthly AS (
    SELECT strftime('%Y-%m', call_date) AS month, COUNT(*) AS calls
    FROM calls
    GROUP BY strftime('%Y-%m', call_date)
)
SELECT
    month,
    calls,
    LAG(calls) OVER (ORDER BY month)                                          AS prev_month,
    ROUND(100.0 * (calls - LAG(calls) OVER (ORDER BY month))
          / LAG(calls) OVER (ORDER BY month), 1)                             AS mom_growth_pct
FROM monthly
ORDER BY month;
```

**Sample output:**

| month | calls | prev_month | mom_growth_pct |
|---|---|---|---|
| 2026-06 | 23,856 |  |  |
| 2026-07 | 24,322 | 23,856 | 2 |

### 8. Running revenue by day

*Cumulative sales total using a running window*

```sql
WITH daily_sales AS (
    SELECT call_date, ROUND(SUM(sale_amount), 0) AS daily_revenue
    FROM calls
    WHERE sale_amount > 0
    GROUP BY call_date
)
SELECT
    call_date,
    daily_revenue,
    ROUND(SUM(daily_revenue) OVER (ORDER BY call_date
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 0) AS running_revenue
FROM daily_sales
ORDER BY call_date
LIMIT 14;
```

**Sample output:**

| call_date | daily_revenue | running_revenue |
|---|---|---|
| 2026-06-01 | 42,037 | 42,037 |
| 2026-06-02 | 59,773 | 101,810 |
| 2026-06-03 | 56,398 | 158,208 |
| 2026-06-04 | 57,436 | 215,644 |
| 2026-06-05 | 53,178 | 268,822 |
| 2026-06-06 | 30,316 | 299,138 |
| 2026-06-07 | 23,065 | 322,203 |
| 2026-06-08 | 50,325 | 372,528 |

### 9. First-contact resolution by campaign type

*FCR% grouped and filtered with HAVING*

```sql
SELECT
    c.campaign_type,
    COUNT(*)                                                 AS answered_calls,
    ROUND(100.0 * SUM(cl.resolved) / COUNT(*), 1)            AS fcr_pct
FROM calls cl
JOIN campaigns c ON c.campaign_id = cl.campaign_id
WHERE cl.answered = 1 AND cl.resolved IS NOT NULL
GROUP BY c.campaign_type
HAVING COUNT(*) > 100
ORDER BY fcr_pct DESC;
```

**Sample output:**

| campaign_type | answered_calls | fcr_pct |
|---|---|---|
| Retentions | 4,367 | 85.9 |
| Sales | 12,877 | 85.8 |
| Tech Support | 4,976 | 85.7 |
| Customer Care | 8,823 | 85.3 |
| Lead Gen | 3,717 | 84.9 |
| Collections | 10,129 | 84.8 |

### 10. Agents flagged for coaching

*Below-target CSAT or FCR, with a coaching reason*

```sql
WITH perf AS (
    SELECT
        a.full_name,
        c.campaign_name,
        COUNT(*)                                       AS calls,
        ROUND(AVG(cl.csat), 2)                         AS csat,
        ROUND(100.0 * SUM(cl.resolved) / COUNT(*), 1)  AS fcr_pct
    FROM calls cl
    JOIN agents    a ON a.agent_id    = cl.agent_id
    JOIN campaigns c ON c.campaign_id = cl.campaign_id
    WHERE cl.answered = 1 AND cl.csat IS NOT NULL
    GROUP BY a.agent_id, a.full_name, c.campaign_name
    HAVING COUNT(*) >= 30
)
SELECT full_name, campaign_name, calls, csat, fcr_pct,
    CASE
        WHEN csat < 3.2 AND fcr_pct < 75 THEN 'CSAT + FCR'
        WHEN csat < 3.2                  THEN 'Low CSAT'
        ELSE 'Low FCR'
    END AS coaching_reason
FROM perf
WHERE csat < 3.2 OR fcr_pct < 75
ORDER BY csat ASC
LIMIT 12;
```

**Sample output:**

_(no rows)_

### 11. Revenue per agent-day

*Sales productivity: revenue divided by active agent-days per campaign*

```sql
WITH agent_days AS (
    SELECT campaign_id, agent_id, call_date
    FROM calls
    WHERE answered = 1
    GROUP BY campaign_id, agent_id, call_date
)
SELECT
    c.campaign_name,
    ROUND(SUM(cl.sale_amount), 0)                            AS revenue,
    COUNT(DISTINCT ad.agent_id || ad.call_date)              AS agent_days,
    ROUND(SUM(cl.sale_amount) * 1.0 /
          COUNT(DISTINCT ad.agent_id || ad.call_date), 0)    AS revenue_per_agent_day
FROM campaigns c
JOIN calls      cl ON cl.campaign_id = c.campaign_id
JOIN agent_days ad ON ad.campaign_id = c.campaign_id
WHERE c.campaign_type IN ('Sales','Lead Gen','Retentions')
GROUP BY c.campaign_name
ORDER BY revenue_per_agent_day DESC;
```

**Sample output:**

| campaign_name | revenue | agent_days | revenue_per_agent_day |
|---|---|---|---|
| DStv Upsell | 663,429,831 | 845 | 785,124 |
| MTN Retentions | 329,943,269 | 607 | 543,564 |
| Vodacom Upgrades | 312,050,699 | 605 | 515,786 |
| Discovery Lead Gen | 253,747,759 | 547 | 463,890 |
| OUTsurance Sales | 179,548,128 | 426 | 421,474 |
