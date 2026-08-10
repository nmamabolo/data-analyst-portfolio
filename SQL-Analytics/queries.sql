-- ============================================================
--  BPO Contact-Centre Analytics — Query Library
--  Author: Neo Mamabolo
--  Written for SQLite (window functions require 3.25+).
--  Each query answers a real operational question a BPO MI /
--  WFM analyst gets asked. Markers "-- @@" label each query so
--  the results can be auto-documented in the README.
-- ============================================================


-- @@ Campaign performance summary | Volume, AHT, answer rate, CSAT and revenue per campaign
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


-- @@ Daily service level | % of calls answered within 20s SLA, by day (last 14 days)
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


-- @@ Top 10 agents by volume | Ranked leaderboard using a window function
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


-- @@ Agent CSAT vs campaign average | Each agent measured against their own campaign benchmark
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


-- @@ Attrition by campaign | Headcount, resignations and attrition rate
SELECT
    c.campaign_name,
    COUNT(*)                                                  AS headcount,
    SUM(CASE WHEN a.status = 'Resigned' THEN 1 ELSE 0 END)    AS resigned,
    ROUND(100.0 * SUM(CASE WHEN a.status = 'Resigned' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_pct
FROM agents a
JOIN campaigns c ON c.campaign_id = a.campaign_id
GROUP BY c.campaign_name
ORDER BY attrition_pct DESC;


-- @@ Tenure cohort analysis | Staff grouped into 0-3 / 3-6 / 6-12 / 12+ month bands
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


-- @@ Month-over-month volume | Call volume with previous month and growth % via LAG
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


-- @@ Running revenue by day | Cumulative sales total using a running window
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


-- @@ First-contact resolution by campaign type | FCR% grouped and filtered with HAVING
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


-- @@ Agents flagged for coaching | Below-target CSAT or FCR, with a coaching reason
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


-- @@ Revenue per agent-day | Sales productivity: revenue divided by active agent-days per campaign
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
