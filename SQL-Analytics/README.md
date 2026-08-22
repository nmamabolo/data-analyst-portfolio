Ten self-contained PostgreSQL projects that turn realistic business questions into reproducible analysis. Each project includes a short case study, a compact synthetic dataset, and commented SQL that can be run from top to bottom.

## Project index

| # | Project | Business question | SQL demonstrated |
|---|---|---|---|
| 1 | [Retail Sales Performance](01-retail-sales/) | Which categories, regions, and months drive revenue? | CTEs, aggregation, `LAG`, contribution % |
| 2 | [Customer Segmentation](02-customer-segmentation/) | Which customers are most valuable or at risk? | RFM, `NTILE`, date arithmetic, scoring |
| 3 | [SaaS Churn & Retention](03-saas-churn/) | Where is recurring revenue being lost? | Cohorts, conditional aggregation, retention |
| 4 | [Marketing Funnel](04-marketing-funnel/) | Which channels convert efficiently? | Funnel metrics, safe division, ranking |
| 5 | [Inventory Optimization](05-inventory-optimization/) | Which products need replenishment? | Rolling demand, stock cover, classification |
| 6 | [Food Delivery Operations](06-food-delivery/) | What causes late deliveries? | Multi-table joins, percentiles, SLA analysis |
| 7 | [Banking Fraud Signals](07-banking-fraud/) | Which transactions exhibit suspicious behavior? | Window frames, anomaly rules, velocity checks |
| 8 | [Employee Attrition](08-employee-attrition/) | Where is employee turnover concentrated? | Rates, benchmarking, correlated comparisons |
| 9 | [Healthcare Appointments](09-healthcare-appointments/) | What predicts patient no-shows? | Feature engineering, rates, scheduling analysis |
| 10 | [Streaming Content Analytics](10-streaming-content/) | What content improves engagement? | Sessionization, completion rates, top-N analysis |

## How to run

Requirements: PostgreSQL 13+ and a client such as `psql`, DBeaver, or pgAdmin.

```bash
psql -d your_database -f 01-retail-sales/solution.sql
```

Every script creates its own schema (`portfolio_01` through `portfolio_10`), so all ten can coexist in one database. The data is deliberately small enough to inspect by hand; the analytical patterns scale to production tables.

## Portfolio highlights

- Business-first problem framing and documented assumptions
- Reproducible schema and sample data—no external downloads required
- Intermediate-to-advanced PostgreSQL patterns
- Readable CTE pipelines and defensive calculations with `NULLIF`
- Action-oriented outputs rather than isolated syntax exercises
