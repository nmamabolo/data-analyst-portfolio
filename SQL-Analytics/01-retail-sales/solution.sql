-- Retail Sales Performance | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_01 CASCADE;
CREATE SCHEMA portfolio_01;
SET search_path TO portfolio_01;

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id INT NOT NULL,
    region TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0
);

INSERT INTO orders VALUES
(1,'2025-01-04',101,'East','Electronics',1,900,10),(2,'2025-01-09',102,'West','Furniture',2,250,0),
(3,'2025-01-18',103,'South','Office',5,30,5),(4,'2025-02-02',101,'East','Office',3,45,0),
(5,'2025-02-12',104,'North','Electronics',2,420,5),(6,'2025-02-22',105,'West','Furniture',1,700,15),
(7,'2025-03-03',106,'South','Electronics',1,1200,0),(8,'2025-03-11',102,'West','Office',8,25,0),
(9,'2025-03-18',107,'North','Furniture',3,310,10),(10,'2025-04-01',108,'East','Electronics',2,550,5),
(11,'2025-04-15',103,'South','Office',10,22,0),(12,'2025-04-25',109,'North','Furniture',1,850,5);

-- Reusable clean metric layer.
CREATE VIEW order_metrics AS
SELECT *, quantity * unit_price * (1 - discount_pct / 100) AS revenue
FROM orders;

-- 1. Monthly KPI trend and growth.
WITH monthly AS (
    SELECT date_trunc('month', order_date)::date AS month,
           ROUND(SUM(revenue),2) AS revenue,
           COUNT(DISTINCT order_id) AS orders,
           COUNT(DISTINCT customer_id) AS customers
    FROM order_metrics GROUP BY 1
), trended AS (
    SELECT *, LAG(revenue) OVER (ORDER BY month) AS prior_revenue FROM monthly
)
SELECT month, revenue, orders, customers,
       ROUND(revenue / NULLIF(orders,0),2) AS avg_order_value,
       ROUND(100 * (revenue-prior_revenue) / NULLIF(prior_revenue,0),1) AS mom_growth_pct
FROM trended ORDER BY month;

-- 2. Category revenue and portfolio contribution.
SELECT category, ROUND(SUM(revenue),2) AS revenue,
       ROUND(100 * SUM(revenue) / SUM(SUM(revenue)) OVER (),1) AS revenue_share_pct
FROM order_metrics GROUP BY category ORDER BY revenue DESC;

-- 3. Rank regions by sales.
SELECT region, ROUND(SUM(revenue),2) AS revenue,
       DENSE_RANK() OVER (ORDER BY SUM(revenue) DESC) AS revenue_rank
FROM order_metrics GROUP BY region ORDER BY revenue_rank;

