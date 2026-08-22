-- Banking Fraud Signals | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_07 CASCADE;
CREATE SCHEMA portfolio_07;
SET search_path TO portfolio_07;

CREATE TABLE transactions (transaction_id INT PRIMARY KEY, customer_id INT, transaction_at TIMESTAMP, amount NUMERIC(10,2), country TEXT, merchant_category TEXT);
INSERT INTO transactions VALUES
(1,101,'2025-06-01 08:00',45,'US','Grocery'),(2,101,'2025-06-03 12:00',60,'US','Dining'),(3,101,'2025-06-04 09:00',55,'US','Fuel'),
(4,101,'2025-06-04 09:12',2400,'GB','Electronics'),(5,101,'2025-06-04 09:20',1900,'GB','Jewelry'),
(6,102,'2025-06-01 10:00',120,'US','Grocery'),(7,102,'2025-06-02 11:00',95,'US','Dining'),(8,102,'2025-06-05 14:00',110,'US','Travel'),
(9,103,'2025-06-01 07:00',30,'CA','Fuel'),(10,103,'2025-06-01 07:10',35,'CA','Grocery'),(11,103,'2025-06-01 07:18',40,'CA','Dining'),
(12,103,'2025-06-01 07:25',42,'CA','Dining'),(13,104,'2025-06-03 16:00',500,'US','Travel'),(14,104,'2025-06-03 17:00',520,'FR','Travel');

WITH history AS (
 SELECT t.*,
   AVG(amount) OVER(PARTITION BY customer_id ORDER BY transaction_at ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) prior_avg_amount,
   COUNT(*) OVER(PARTITION BY customer_id ORDER BY transaction_at RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW) txns_30m,
   LAG(country) OVER(PARTITION BY customer_id ORDER BY transaction_at) prior_country,
   LAG(transaction_at) OVER(PARTITION BY customer_id ORDER BY transaction_at) prior_time
 FROM transactions t
), rules AS (
 SELECT *,
   (prior_avg_amount IS NOT NULL AND amount>5*prior_avg_amount AND amount>500) large_amount_flag,
   (txns_30m>=4) velocity_flag,
   (prior_country IS NOT NULL AND country<>prior_country AND transaction_at-prior_time<interval '2 hours') rapid_country_change_flag
 FROM history
), scored AS (
 SELECT *,large_amount_flag::int*50+velocity_flag::int*30+rapid_country_change_flag::int*40 risk_score FROM rules
)
SELECT transaction_id,customer_id,transaction_at,amount,country,merchant_category,
 large_amount_flag,velocity_flag,rapid_country_change_flag,risk_score,
 CASE WHEN risk_score>=50 THEN 'High' WHEN risk_score>=30 THEN 'Medium' ELSE 'Low' END review_priority
FROM scored WHERE risk_score>0 ORDER BY risk_score DESC,transaction_at;

-- Daily monitoring summary.
WITH x AS (SELECT transaction_at::date day,COUNT(*) txn_count,SUM(amount) volume,COUNT(*) FILTER(WHERE amount>=1000) high_value_count FROM transactions GROUP BY 1)
SELECT day,txn_count,volume,high_value_count,ROUND(volume/NULLIF(txn_count,0),2) avg_ticket FROM x ORDER BY day;

