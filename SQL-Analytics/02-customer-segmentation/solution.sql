-- Customer Segmentation (RFM) | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_02 CASCADE;
CREATE SCHEMA portfolio_02;
SET search_path TO portfolio_02;

CREATE TABLE customers (customer_id INT PRIMARY KEY, customer_name TEXT, signup_date DATE);
CREATE TABLE purchases (purchase_id INT PRIMARY KEY, customer_id INT REFERENCES customers, purchased_at DATE, amount NUMERIC(10,2));
INSERT INTO customers VALUES (1,'Ava','2024-01-10'),(2,'Ben','2024-03-15'),(3,'Chloe','2024-06-20'),(4,'Diego','2024-08-01'),(5,'Emma','2024-09-12'),(6,'Farah','2024-11-05'),(7,'Gus','2025-01-08'),(8,'Hana','2025-02-14');
INSERT INTO purchases VALUES
(1,1,'2025-05-20',800),(2,1,'2025-06-12',450),(3,1,'2025-06-25',600),(4,2,'2025-01-10',120),
(5,2,'2025-02-18',90),(6,3,'2025-06-28',250),(7,3,'2025-06-29',280),(8,4,'2024-11-05',1000),
(9,5,'2025-04-12',75),(10,5,'2025-06-02',85),(11,6,'2025-06-20',500),(12,7,'2025-03-01',40),
(13,7,'2025-03-20',35),(14,7,'2025-04-02',45),(15,8,'2025-06-27',150);

WITH analysis_date AS (SELECT DATE '2025-07-01' AS dt),
rfm AS (
  SELECT c.customer_id, c.customer_name,
         (a.dt - MAX(p.purchased_at))::int AS recency_days,
         COUNT(p.purchase_id) AS frequency,
         COALESCE(SUM(p.amount),0) AS monetary
  FROM customers c CROSS JOIN analysis_date a
  LEFT JOIN purchases p USING (customer_id)
  GROUP BY c.customer_id,c.customer_name,a.dt
), scored AS (
  SELECT *,
         NTILE(4) OVER (ORDER BY recency_days DESC NULLS FIRST) AS r_score,
         NTILE(4) OVER (ORDER BY frequency) AS f_score,
         NTILE(4) OVER (ORDER BY monetary) AS m_score
  FROM rfm
), segmented AS (
  SELECT *,
    CASE WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
         WHEN r_score >= 3 AND f_score >= 2 THEN 'Loyal'
         WHEN r_score <= 2 AND (f_score >= 3 OR m_score >= 3) THEN 'At Risk'
         ELSE 'Needs Attention' END AS segment
  FROM scored
)
SELECT customer_id, customer_name, recency_days, frequency, monetary,
       r_score, f_score, m_score, segment
FROM segmented ORDER BY segment, monetary DESC;

-- Executive segment summary.
WITH rfm AS (
  SELECT c.customer_id, DATE '2025-07-01'-MAX(p.purchased_at) recency, COUNT(p.purchase_id) frequency, COALESCE(SUM(p.amount),0) monetary
  FROM customers c LEFT JOIN purchases p USING(customer_id) GROUP BY c.customer_id
), bands AS (
  SELECT *, NTILE(4) OVER(ORDER BY recency DESC NULLS FIRST) r, NTILE(4) OVER(ORDER BY frequency) f, NTILE(4) OVER(ORDER BY monetary) m FROM rfm
)
SELECT CASE WHEN r>=3 AND f>=3 AND m>=3 THEN 'Champions' WHEN r>=3 AND f>=2 THEN 'Loyal' WHEN r<=2 AND (f>=3 OR m>=3) THEN 'At Risk' ELSE 'Needs Attention' END segment,
       COUNT(*) customers, ROUND(SUM(monetary),2) lifetime_value
FROM bands GROUP BY 1 ORDER BY lifetime_value DESC;

