-- Marketing Funnel | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_04 CASCADE;
CREATE SCHEMA portfolio_04;
SET search_path TO portfolio_04;

CREATE TABLE campaigns (channel TEXT PRIMARY KEY, spend NUMERIC(10,2));
CREATE TABLE events (user_id INT, channel TEXT REFERENCES campaigns, event_name TEXT, event_at TIMESTAMP, revenue NUMERIC(10,2) DEFAULT 0);
INSERT INTO campaigns VALUES ('Organic',500),('Paid Search',1800),('Social',1200),('Email',400);
INSERT INTO events VALUES
(1,'Organic','visit','2025-06-01 09:00',0),(1,'Organic','signup','2025-06-01 09:05',0),(1,'Organic','purchase','2025-06-02 10:00',120),
(2,'Paid Search','visit','2025-06-01 11:00',0),(2,'Paid Search','signup','2025-06-01 11:10',0),
(3,'Paid Search','visit','2025-06-02 08:00',0),(4,'Social','visit','2025-06-02 12:00',0),(4,'Social','signup','2025-06-02 12:20',0),(4,'Social','purchase','2025-06-04 14:00',80),
(5,'Social','visit','2025-06-03 15:00',0),(6,'Email','visit','2025-06-04 09:00',0),(6,'Email','signup','2025-06-04 09:03',0),(6,'Email','purchase','2025-06-04 09:30',200),
(7,'Email','visit','2025-06-04 10:00',0),(7,'Email','signup','2025-06-04 10:05',0),(8,'Organic','visit','2025-06-05 07:00',0),(8,'Organic','signup','2025-06-05 07:08',0),
(9,'Paid Search','visit','2025-06-06 18:00',0),(9,'Paid Search','signup','2025-06-06 18:15',0),(9,'Paid Search','purchase','2025-06-07 08:00',300),(10,'Social','visit','2025-06-07 13:00',0);

WITH user_funnels AS (
 SELECT channel,user_id,
   BOOL_OR(event_name='visit') visited, BOOL_OR(event_name='signup') signed_up,
   BOOL_OR(event_name='purchase') purchased, SUM(revenue) revenue
 FROM events GROUP BY channel,user_id
), channel_metrics AS (
 SELECT c.channel,c.spend,COUNT(*) FILTER(WHERE visited) visitors,
   COUNT(*) FILTER(WHERE signed_up) signups,COUNT(*) FILTER(WHERE purchased) customers,SUM(revenue) revenue
 FROM campaigns c LEFT JOIN user_funnels f USING(channel) GROUP BY c.channel,c.spend
)
SELECT *,
 ROUND(100.0*signups/NULLIF(visitors,0),1) visit_to_signup_pct,
 ROUND(100.0*customers/NULLIF(signups,0),1) signup_to_purchase_pct,
 ROUND(100.0*customers/NULLIF(visitors,0),1) overall_conversion_pct,
 ROUND(spend/NULLIF(customers,0),2) customer_acquisition_cost,
 ROUND(revenue/NULLIF(visitors,0),2) revenue_per_visitor,
 DENSE_RANK() OVER(ORDER BY revenue/NULLIF(spend,0) DESC NULLS LAST) roas_rank
FROM channel_metrics ORDER BY roas_rank;

