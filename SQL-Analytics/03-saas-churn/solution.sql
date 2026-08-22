-- SaaS Churn & Retention | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_03 CASCADE;
CREATE SCHEMA portfolio_03;
SET search_path TO portfolio_03;

CREATE TABLE subscriptions (customer_id INT PRIMARY KEY, started_on DATE, cancelled_on DATE, monthly_price NUMERIC(10,2), plan TEXT);
INSERT INTO subscriptions VALUES
(1,'2025-01-05',NULL,99,'Pro'),(2,'2025-01-12','2025-04-10',49,'Starter'),(3,'2025-01-25','2025-03-03',49,'Starter'),
(4,'2025-02-02',NULL,199,'Business'),(5,'2025-02-18','2025-06-15',99,'Pro'),(6,'2025-03-09',NULL,49,'Starter'),
(7,'2025-03-20','2025-05-02',99,'Pro'),(8,'2025-04-04',NULL,199,'Business'),(9,'2025-05-16',NULL,49,'Starter'),(10,'2025-06-01',NULL,99,'Pro');

-- Month-end customer and recurring-revenue snapshot.
WITH months AS (
  SELECT d::date AS month_start, (d + interval '1 month')::date AS next_month
  FROM generate_series('2025-01-01'::date,'2025-06-01'::date,'1 month') d
)
SELECT m.month_start,
       COUNT(s.customer_id) FILTER (WHERE s.started_on < m.next_month AND (s.cancelled_on IS NULL OR s.cancelled_on >= m.next_month)) active_customers,
       COALESCE(SUM(s.monthly_price) FILTER (WHERE s.started_on < m.next_month AND (s.cancelled_on IS NULL OR s.cancelled_on >= m.next_month)),0) mrr
FROM months m CROSS JOIN subscriptions s GROUP BY m.month_start ORDER BY m.month_start;

-- Logo churn: cancellations during month / customers active at month start.
WITH months AS (
 SELECT d::date month_start,(d+interval '1 month')::date next_month FROM generate_series('2025-02-01'::date,'2025-06-01'::date,'1 month') d
), metrics AS (
 SELECT m.month_start,
   COUNT(*) FILTER(WHERE s.started_on < m.month_start AND (s.cancelled_on IS NULL OR s.cancelled_on >= m.month_start)) opening_customers,
   COUNT(*) FILTER(WHERE s.cancelled_on >= m.month_start AND s.cancelled_on < m.next_month) churned_customers
 FROM months m CROSS JOIN subscriptions s GROUP BY 1
)
SELECT *, ROUND(100.0*churned_customers/NULLIF(opening_customers,0),1) churn_rate_pct FROM metrics ORDER BY month_start;

-- Cohort retention in long format (ideal BI input).
WITH months AS (
 SELECT d::date month_start FROM generate_series('2025-01-01'::date,'2025-06-01'::date,'1 month') d
), cohorts AS (
 SELECT *,date_trunc('month',started_on)::date cohort_month FROM subscriptions
), retention AS (
 SELECT c.cohort_month,m.month_start,
   ((EXTRACT(YEAR FROM age(m.month_start,c.cohort_month))*12 + EXTRACT(MONTH FROM age(m.month_start,c.cohort_month))))::int month_number,
   COUNT(*) FILTER(WHERE c.started_on < m.month_start+interval '1 month' AND (c.cancelled_on IS NULL OR c.cancelled_on >= m.month_start+interval '1 month')) retained
 FROM cohorts c JOIN months m ON m.month_start>=c.cohort_month GROUP BY 1,2
)
SELECT *, ROUND(100.0*retained/NULLIF(MAX(retained) OVER(PARTITION BY cohort_month),0),1) retention_pct
FROM retention ORDER BY cohort_month,month_number;

