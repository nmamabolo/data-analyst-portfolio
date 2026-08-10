# 🛠️ Build Guide — reproducing the `.pbix` in Power BI Desktop

Follow these steps to turn the CSV dataset into the live report and export a `.pbix`.

## 1 · Get the data in
1. Open **Power BI Desktop** → **Home → Get data → Text/CSV**.
2. Import all four files from [`/data`](./data): `dim_campaign.csv`, `dim_agent.csv`, `dim_date.csv`, `fact_daily_performance.csv`.
3. In **Transform data (Power Query)**, confirm data types:
   - dates → **Date**; ids and counts → **Whole number**; `target_service_level`, `revenue` → **Decimal**.
   - `is_weekend` → Whole number (0/1). **Close & Apply.**

## 2 · Model the relationships (Model view)
Create these **one-to-many** relationships (single-direction filter, dimension → fact):

| From (one) | To (many) | On |
|---|---|---|
| `dim_campaign[campaign_id]` | `fact_daily_performance[campaign_id]` | campaign_id |
| `dim_agent[agent_id]` | `fact_daily_performance[agent_id]` | agent_id |
| `dim_date[date]` | `fact_daily_performance[date]` | date |

Then select `dim_date` → **Table tools → Mark as date table** (using `date`). This enables the time-intelligence measures.

## 3 · Add the measures
1. **Home → Enter data** → create an empty table named `_Measures` (one throwaway column) so measures have a tidy home.
2. Paste each measure from [`DAX_measures.md`](./DAX_measures.md) via **New measure**.
3. Set the formats from the table at the bottom of that file.

## 4 · Build the pages
Recreate the three pages from the [README](./README.md#️-report-pages):

**Executive Overview**
- Row of **Card / KPI** visuals: `Calls Handled`, `Service Level %`, `Avg CSAT`, `Total Revenue`, `Attrition Rate %`.
- **Line chart:** `Service Level %` by `dim_date[date]`.
- **Clustered bar:** `Total Revenue` by `dim_campaign[campaign_name]`.
- **Table / matrix:** campaign, `Service Level %`, `SL vs Target`, `SL RAG` (apply conditional formatting on the RAG column).
- **Slicers:** `dim_date[month_name]` and `dim_campaign[campaign_name]`.

**Campaign Performance** — cost vs revenue bar, `Service Level %` vs `Target Service Level`, `Conversion Rate %`, `AHT (sec)` and `Abandon Rate %` cards.

**Agent Scorecard** — matrix of agents with `Calls Handled`, `AHT (sec)`, `Avg CSAT`, `Agent Revenue Rank`; scatter of calls vs AHT; team/campaign slicers.

## 5 · Polish & export
- Apply a consistent theme (**View → Themes**), align visuals to the grid, add page titles.
- Add **drill-through** from campaign → Agent Scorecard if you want.
- **File → Save** as `Campaign_Performance_Dashboard.pbix` and commit it to this folder.

> Once you export the `.pbix`, drop a screenshot in here too and update the image link in the README.
