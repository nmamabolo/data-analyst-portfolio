# 📈 Advanced Excel Analytics Portfolio — BPO Operations

An advanced, multi-sheet set of Excel models built for a **multi-campaign BPO / contact-centre environment**. Where the [starter portfolio](../Excel-Portfolio) shows clean single-purpose sheets, this set demonstrates **end-to-end analytical models**: raw operational data feeding live dashboards through `SUMIF`/`COUNTIFS`/`AVERAGEIF`, `INDEX`/`MATCH`, `SUMPRODUCT`, cohort logic and staffing formulas.

> All data is realistic **sample** data for demonstration — no real people, customers or companies. Localised to South African conventions (ZAR, PAYE/UIF, campaign clients).

---

## 📁 Workbooks

### 01 — Campaign Cost & Profitability Analysis
A 12-campaign P&L model. Four linked sheets: **Campaigns** master → **CostData** (fully-loaded cost stack: labour, telephony, technology, facilities, training, overhead × 6 months) → **Production** (volume, conversions, revenue) → **P&L Dashboard**.
- Per-campaign **cost, revenue, gross profit, margin %, cost-per-contact, cost-per-sale, revenue-per-FTE, ROI**, ranked
- Company cost-stack breakdown + charts
- *Answers: "how much does each campaign cost, and what does it produce?"*

### 02 — HR Attrition & Tenure Cohort Analysis ⭐
220-employee master with **live tenure & cohort formulas**, feeding a deep attrition dashboard.
- Tenure **cohorts: 0–3 / 3–6 / 6–12 / 12+ months** — headcount, % of total, and **attrition rate within each cohort**
- **Gender × cohort matrix**, % female, % of females still employed, female vs male attrition
- **Early attrition** (<3 months), attrition by department & campaign, monthly resignation trend
- 4 charts (cohort split, attrition by cohort/campaign, monthly trend)

### 03 — Workforce Capacity & Shrinkage Model
Erlang-style staffing model across 12 campaigns × 4 weeks.
- Contacts × AHT → productive hours → **Required FTE** (net of shrinkage & target occupancy)
- Required vs **Scheduled FTE**, variance, coverage %, colour-coded **service-risk** flags
- Capacity dashboard with required-vs-scheduled by campaign

### 04 — Agent Performance & QA Scorecard
150 agents, **weighted 6-metric composite** (QA, CSAT, adherence, attendance, productivity, conversion).
- **Overall rank + rank-within-campaign** (`SUMPRODUCT`), quintiles, automated **coaching flags**
- Per-campaign benchmarks (`AVERAGEIF`) and top performer (`INDEX`/`MATCH`)

### 05 — Budget vs Actual Tracker
Operating budget across 8 cost centres × 6 months.
- Monthly **variance & variance %**, over/under-budget flags
- YTD dashboard by cost centre with budget-vs-actual chart

### 06 — Customer Experience Analytics
240 survey responses integrating **CSAT, NPS, QA and FCR**.
- Overall KPIs + segmentation **by campaign, channel and month**
- Proper **NPS** (promoters − detractors) and first-contact-resolution rates, with charts

### 07 — Client SLA Performance Scorecard
Contractual SLA management across 12 client campaigns. Three linked sheets: **SLA Targets** → **SLA Actuals** (6 months) → **SLA Scorecard**.
- Latest-month actual (`AVERAGEIFS`) vs contractual target (`INDEX`/`MATCH`), **direction-aware** Met/Miss per metric (Service Level, CSAT, QA, ASA, Abandon)
- **RAG status**, SLA attainment %, and **breach-penalty modelling** per campaign
- Green/Amber/Red roll-up, company service-level trend, charts

### 08 — Intraday / Interval Performance Tracker
Real-time WFM view of a single campaign across 24 × 30-minute intervals.
- **Forecast vs actual volume**, forecast accuracy, Required vs Scheduled agents, coverage
- Modelled **service level per interval**, ASA, occupancy, adherence, and below-SL flags
- Day summary + forecast-vs-actual and SL-by-interval charts

---

## 🛠️ Techniques on show
`SUMIF` / `SUMIFS` · `COUNTIF` / `COUNTIFS` · `AVERAGEIF` · `INDEX`/`MATCH` · `SUMPRODUCT` · `RANK` · `IFERROR` · nested `IF` · date-range `COUNTIFS` for cohorts · staffing/capacity formulas · multi-sheet data models · dashboards, KPI cards, conditional formatting, colour scales, and 12 charts across the set.

📫 Contact: *nmamabolo566@gmail.com*
