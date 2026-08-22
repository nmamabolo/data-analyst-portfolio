-- Employee Attrition | PostgreSQL 13+
DROP SCHEMA IF EXISTS portfolio_08 CASCADE;
CREATE SCHEMA portfolio_08;
SET search_path TO portfolio_08;

CREATE TABLE employees (employee_id INT PRIMARY KEY, department TEXT, hire_date DATE, exit_date DATE, work_mode TEXT, performance_rating INT, manager_id INT);
INSERT INTO employees VALUES
(1,'Engineering','2021-01-10',NULL,'Remote',4,90),(2,'Engineering','2023-03-01','2025-04-15','Hybrid',3,90),(3,'Engineering','2024-08-12',NULL,'Hybrid',5,91),
(4,'Sales','2022-02-20','2025-02-01','Onsite',3,92),(5,'Sales','2024-01-10','2025-05-30','Remote',2,92),(6,'Sales','2020-06-15',NULL,'Hybrid',4,93),
(7,'Support','2024-11-01','2025-03-12','Onsite',3,94),(8,'Support','2023-07-07',NULL,'Remote',4,94),(9,'Support','2022-09-09',NULL,'Onsite',4,95),
(10,'Finance','2019-04-22',NULL,'Hybrid',5,96),(11,'Finance','2024-06-01','2025-06-10','Remote',3,96),(12,'Finance','2021-12-02',NULL,'Onsite',4,97),
(13,'Engineering','2025-01-05',NULL,'Remote',4,91),(14,'Sales','2025-02-10',NULL,'Onsite',3,93),(15,'Support','2021-05-15','2025-01-15','Remote',3,95),(16,'Finance','2023-10-18',NULL,'Hybrid',4,97);

-- Employees active at any point in 2025 form the population; 2025 exits are attrition.
WITH base AS (
 SELECT *,EXTRACT(YEAR FROM age(COALESCE(exit_date,DATE '2025-12-31'),hire_date)) tenure_years,
   (exit_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31') exited_2025
 FROM employees WHERE hire_date<=DATE '2025-12-31' AND (exit_date IS NULL OR exit_date>=DATE '2025-01-01')
), company AS (SELECT AVG(exited_2025::int) company_rate FROM base), dept AS (
 SELECT department,COUNT(*) headcount,COUNT(*) FILTER(WHERE exited_2025) exits,AVG(exited_2025::int) attrition_rate FROM base GROUP BY department
)
SELECT d.department,d.headcount,d.exits,ROUND(100*d.attrition_rate,1) attrition_pct,
 ROUND(100*c.company_rate,1) company_attrition_pct,ROUND(100*(d.attrition_rate-c.company_rate),1) variance_points
FROM dept d CROSS JOIN company c ORDER BY attrition_pct DESC;

WITH base AS (
 SELECT *,EXTRACT(YEAR FROM age(COALESCE(exit_date,DATE '2025-12-31'),hire_date)) tenure,
 (exit_date BETWEEN '2025-01-01' AND '2025-12-31') exited FROM employees
)
SELECT CASE WHEN tenure<1 THEN '<1 year' WHEN tenure<3 THEN '1-2 years' WHEN tenure<5 THEN '3-4 years' ELSE '5+ years' END tenure_band,
 COUNT(*) employees,COUNT(*) FILTER(WHERE exited) exits,ROUND(100.0*AVG(exited::int),1) attrition_pct
FROM base GROUP BY 1 ORDER BY MIN(tenure);

SELECT work_mode,COUNT(*) employees,COUNT(*) FILTER(WHERE exit_date BETWEEN '2025-01-01' AND '2025-12-31') exits,
 ROUND(100.0*AVG((exit_date BETWEEN '2025-01-01' AND '2025-12-31')::int),1) attrition_pct
FROM employees GROUP BY work_mode ORDER BY attrition_pct DESC;

