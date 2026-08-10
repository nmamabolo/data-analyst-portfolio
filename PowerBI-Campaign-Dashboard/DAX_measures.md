# DAX Measures Library — Campaign Performance Dashboard

Create a measures table (or add to `fact_daily_performance`) and paste these in. They assume the star schema described in the [README](./README.md): `dim_campaign`, `dim_agent`, `dim_date` all related **one-to-many** to `fact_daily_performance`.

> Tip: put every measure in a dedicated **`_Measures`** table to keep the model tidy.

---

## 1 · Volume & Efficiency

```dax
Calls Offered = SUM ( fact_daily_performance[calls_offered] )

Calls Handled = SUM ( fact_daily_performance[calls_handled] )

Calls Abandoned = SUM ( fact_daily_performance[calls_abandoned] )

Answer Rate % =
DIVIDE ( [Calls Handled], [Calls Offered] )

Abandon Rate % =
DIVIDE ( [Calls Abandoned], [Calls Offered] )

AHT (sec) =
DIVIDE ( SUM ( fact_daily_performance[handle_sec_total] ), [Calls Handled] )

Service Level % =
DIVIDE ( SUM ( fact_daily_performance[sla_within_20s] ), [Calls Offered] )
```

## 2 · Quality

```dax
Avg CSAT =
DIVIDE ( SUM ( fact_daily_performance[csat_sum] ), SUM ( fact_daily_performance[csat_count] ) )

CSAT Responses = SUM ( fact_daily_performance[csat_count] )

FCR % =
DIVIDE ( SUM ( fact_daily_performance[resolved_count] ), [Calls Handled] )
```

## 3 · Sales & Revenue

```dax
Total Revenue = SUM ( fact_daily_performance[revenue] )

Total Sales = SUM ( fact_daily_performance[sales_count] )

Conversion Rate % =
DIVIDE ( [Total Sales], [Calls Handled] )

Revenue per Agent =
DIVIDE ( [Total Revenue], [Active Agents] )
```

## 4 · Workforce & Attrition

```dax
Active Agents =
CALCULATE ( DISTINCTCOUNT ( dim_agent[agent_id] ), dim_agent[status] = "Active" )

Total Headcount = DISTINCTCOUNT ( dim_agent[agent_id] )

Resigned Agents =
CALCULATE ( DISTINCTCOUNT ( dim_agent[agent_id] ), dim_agent[status] = "Resigned" )

Attrition Rate % =
DIVIDE ( [Resigned Agents], [Total Headcount] )

% Female =
DIVIDE (
    CALCULATE ( DISTINCTCOUNT ( dim_agent[agent_id] ), dim_agent[gender] = "Female" ),
    [Total Headcount]
)
```

## 5 · Targets & RAG variance

```dax
Target Service Level =
AVERAGE ( dim_campaign[target_service_level] )

SL vs Target =
[Service Level %] - [Target Service Level]

SL RAG =
VAR v = [SL vs Target]
RETURN
    SWITCH ( TRUE (),
        v >= 0,      "🟢 On target",
        v >= -0.05,  "🟡 At risk",
        "🔴 Breach"
    )
```

## 6 · Time intelligence (needs a marked date table)

```dax
Calls Handled LM =
CALCULATE ( [Calls Handled], DATEADD ( dim_date[date], -1, MONTH ) )

Calls MoM % =
DIVIDE ( [Calls Handled] - [Calls Handled LM], [Calls Handled LM] )

Revenue MTD =
TOTALMTD ( [Total Revenue], dim_date[date] )

Revenue Running Total =
CALCULATE (
    [Total Revenue],
    FILTER ( ALLSELECTED ( dim_date[date] ), dim_date[date] <= MAX ( dim_date[date] ) )
)
```

## 7 · Ranking

```dax
Agent Revenue Rank =
IF (
    HASONEVALUE ( dim_agent[agent_name] ),
    RANKX ( ALLSELECTED ( dim_agent[agent_name] ), [Total Revenue],, DESC )
)

Campaign SL Rank =
IF (
    HASONEVALUE ( dim_campaign[campaign_name] ),
    RANKX ( ALLSELECTED ( dim_campaign[campaign_name] ), [Service Level %],, DESC )
)
```

---

### Suggested formatting
| Measure | Format |
|---|---|
| Answer/Abandon/Service Level/CSAT-derived %, Conversion, Attrition, MoM | Percentage, 1 dp |
| AHT (sec) | Whole number, suffix “s” |
| Avg CSAT | Decimal, 2 dp |
| Total Revenue / Revenue per Agent | Currency (R), 0 dp |
| Rank measures | Whole number |
