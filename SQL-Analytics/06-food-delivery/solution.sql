-- Food Delivery Operations | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_06 CASCADE;
CREATE SCHEMA portfolio_06;
SET search_path TO portfolio_06;

CREATE TABLE restaurants (restaurant_id INT PRIMARY KEY, restaurant_name TEXT, cuisine TEXT);
CREATE TABLE couriers (courier_id INT PRIMARY KEY, courier_name TEXT);
CREATE TABLE deliveries (delivery_id INT PRIMARY KEY, restaurant_id INT REFERENCES restaurants, courier_id INT REFERENCES couriers, ordered_at TIMESTAMP, delivered_at TIMESTAMP, promised_minutes INT, weather TEXT, distance_km NUMERIC(5,1));
INSERT INTO restaurants VALUES (1,'Taco Town','Mexican'),(2,'Green Bowl','Healthy'),(3,'Pasta Place','Italian');
INSERT INTO couriers VALUES (1,'Mia'),(2,'Noah'),(3,'Omar');
INSERT INTO deliveries VALUES
(1,1,1,'2025-06-01 12:00','2025-06-01 12:28',30,'Clear',3.2),(2,1,2,'2025-06-01 18:00','2025-06-01 18:44',35,'Rain',5.1),
(3,2,1,'2025-06-02 11:30','2025-06-02 11:55',30,'Clear',2.4),(4,2,3,'2025-06-02 19:10','2025-06-02 20:03',40,'Storm',6.8),
(5,3,2,'2025-06-03 17:00','2025-06-03 17:38',40,'Clear',4.0),(6,3,3,'2025-06-03 20:00','2025-06-03 20:51',45,'Rain',7.2),
(7,1,1,'2025-06-04 12:15','2025-06-04 12:47',30,'Clear',3.5),(8,2,2,'2025-06-04 18:20','2025-06-04 18:49',35,'Rain',2.8),
(9,3,1,'2025-06-05 19:00','2025-06-05 19:42',45,'Clear',5.5),(10,1,3,'2025-06-05 21:00','2025-06-05 21:58',40,'Storm',8.0);

CREATE VIEW delivery_metrics AS
SELECT d.*,EXTRACT(EPOCH FROM(delivered_at-ordered_at))/60.0 actual_minutes,
       EXTRACT(EPOCH FROM(delivered_at-ordered_at))/60.0<=promised_minutes on_time
FROM deliveries d;

-- Marketplace SLA dashboard.
SELECT COUNT(*) deliveries,
 ROUND(100.0*AVG(on_time::int),1) on_time_pct,
 ROUND(percentile_cont(.5) WITHIN GROUP(ORDER BY actual_minutes)::numeric,1) p50_minutes,
 ROUND(percentile_cont(.9) WITHIN GROUP(ORDER BY actual_minutes)::numeric,1) p90_minutes
FROM delivery_metrics;

-- Restaurant scorecard.
SELECT r.restaurant_name,COUNT(*) deliveries,ROUND(AVG(d.actual_minutes)::numeric,1) avg_minutes,
 ROUND(100.0*AVG(d.on_time::int),1) on_time_pct,
 ROUND(AVG(GREATEST(d.actual_minutes-d.promised_minutes,0))::numeric,1) avg_late_minutes
FROM delivery_metrics d JOIN restaurants r USING(restaurant_id)
GROUP BY r.restaurant_name ORDER BY on_time_pct,deliveries DESC;

-- Environmental and courier diagnostic views.
SELECT weather,COUNT(*) deliveries,ROUND(AVG(actual_minutes)::numeric,1) avg_minutes,ROUND(100.0*AVG(on_time::int),1) on_time_pct
FROM delivery_metrics GROUP BY weather ORDER BY on_time_pct;
SELECT c.courier_name,COUNT(*) deliveries,ROUND(AVG(d.actual_minutes)::numeric,1) avg_minutes,ROUND(100.0*AVG(d.on_time::int),1) on_time_pct
FROM delivery_metrics d JOIN couriers c USING(courier_id) GROUP BY c.courier_name ORDER BY on_time_pct DESC;

