-- Inventory Optimization | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_05 CASCADE;
CREATE SCHEMA portfolio_05;
SET search_path TO portfolio_05;

CREATE TABLE products (product_id INT PRIMARY KEY, product_name TEXT, stock_on_hand INT, lead_time_days INT, safety_stock INT, unit_cost NUMERIC(10,2));
CREATE TABLE daily_sales (sale_date DATE, product_id INT REFERENCES products, units_sold INT, PRIMARY KEY(sale_date,product_id));
INSERT INTO products VALUES (1,'Wireless Mouse',45,7,15,18),(2,'Mechanical Keyboard',12,14,10,55),(3,'USB-C Hub',80,10,20,32),(4,'Laptop Stand',6,12,8,27),(5,'Webcam',120,8,15,42);
INSERT INTO daily_sales VALUES
('2025-06-24',1,8),('2025-06-25',1,7),('2025-06-26',1,9),('2025-06-27',1,6),('2025-06-28',1,10),('2025-06-29',1,8),('2025-06-30',1,9),
('2025-06-24',2,2),('2025-06-25',2,3),('2025-06-26',2,2),('2025-06-27',2,4),('2025-06-28',2,3),('2025-06-29',2,2),('2025-06-30',2,3),
('2025-06-24',3,5),('2025-06-25',3,4),('2025-06-26',3,6),('2025-06-27',3,5),('2025-06-28',3,4),('2025-06-29',3,5),('2025-06-30',3,6),
('2025-06-24',4,1),('2025-06-25',4,2),('2025-06-26',4,2),('2025-06-27',4,1),('2025-06-28',4,3),('2025-06-29',4,2),('2025-06-30',4,2),
('2025-06-24',5,1),('2025-06-25',5,0),('2025-06-26',5,2),('2025-06-27',5,1),('2025-06-28',5,1),('2025-06-29',5,0),('2025-06-30',5,1);

WITH demand AS (
 SELECT p.*,COALESCE(AVG(s.units_sold),0) avg_daily_demand,SUM(s.units_sold) units_sold_7d
 FROM products p LEFT JOIN daily_sales s USING(product_id) GROUP BY p.product_id
), policy AS (
 SELECT *,CEIL(avg_daily_demand*lead_time_days+safety_stock) reorder_point,
   ROUND(stock_on_hand/NULLIF(avg_daily_demand,0),1) days_of_cover
 FROM demand
)
SELECT product_id,product_name,stock_on_hand,ROUND(avg_daily_demand,2) avg_daily_demand,
 lead_time_days,safety_stock,reorder_point,days_of_cover,
 GREATEST(CEIL(avg_daily_demand*(lead_time_days+14)+safety_stock-stock_on_hand),0) recommended_order_qty,
 CASE WHEN stock_on_hand<=safety_stock THEN 'Critical'
      WHEN stock_on_hand<=reorder_point THEN 'Reorder'
      WHEN days_of_cover>60 THEN 'Overstocked' ELSE 'Healthy' END inventory_status
FROM policy ORDER BY CASE WHEN stock_on_hand<=safety_stock THEN 1 WHEN stock_on_hand<=reorder_point THEN 2 ELSE 3 END,days_of_cover;

-- Capital currently tied up by SKU.
SELECT product_name,stock_on_hand,unit_cost,ROUND(stock_on_hand*unit_cost,2) inventory_value
FROM products ORDER BY inventory_value DESC;
