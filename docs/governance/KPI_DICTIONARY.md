# KPI dictionary

One definition per KPI for the three businesses. The DAX is the measure text of the Power BI model (generated from `src/build_tmdl.py`, so the document and the model cannot drift apart). The SQL runs on the processed tables with DuckDB each time this file is rebuilt; its result is compared with the Python pipeline (`src/analysis.py`) for Jan-Oct 2026. Data: SIMULATED, illustrative.

| # | KPI | SQL (Jan-Oct 2026) | Python | Match |
|---|---|---|---|---|
| 1 | New business won (net awards) | $255.96m | $255.96m | yes |
| 2 | Deals won and average deal size | $0.46m | - | - |
| 3 | Open pipeline | $246.56m | $246.56m | yes |
| 4 | Weighted pipeline | $75.54m | $75.54m | yes |
| 5 | Win rate (count) | 48.4% | 48.4% | yes |
| 6 | Win rate (value) | 32.9% | - | - |
| 7 | Proposal conversion (funnel) | 81.0% | - | - |
| 8 | Sales cycle (days) | 60.0 | - | - |
| 9 | Book-to-bill | 1.086x | 1.086x | yes |
| 10 | Order book | $498.48m | $498.48m | yes |
| 11 | Cancellation rate | 1.8% | - | - |
| 12 | Attainment vs target | 95.2% | 95.2% | yes |
| 13 | Variance decomposition | - | - | - |
| 14 | Cross-sell share | - | 66.4% | - |
| 15 | Data freshness and quality | 1.0 | 1.0 | yes |

Conventions: amounts in USD (group reporting currency, as in the group's filed accounts since FY2024); FX = ECB monthly average of the month of the event; a month not yet published uses the last published month and is flagged (`fx_provisional`). Periods are calendar months; YTD = calendar year to date; PY = same period last year.

## 1. New business won (net awards)

**Question.** How much new business did we sign?  
**Definition.** Value of contracts signed in the period, in USD at the ECB monthly average of the signature month.  
**Grain.** opportunity x signature date · **Exclusions.** duplicates excluded; PV scope of integrated deals counted once (in PV); verbal awards excluded · **Owner.** Commercial Analytics (definition) · business sales ops (inputs)  
**Differences between businesses.** CRO: contract value (EUR), win = 'Contracted', not 'Awarded'. PV: total contract value = annual value x years (USD); PV teams also track ACV, kept in acv_usd. ADAMAS: confirmed audit quote (GBP).

DAX (measures in `_Measures`):

```dax
New Business Won =
    CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[status] = "Won" )

New Business Won PY =
    CALCULATE ( [New Business Won], SAMEPERIODLASTYEAR ( DimDate[date] ) )

New Business Won YoY % =
    DIVIDE ( [New Business Won] - [New Business Won PY], [New Business Won PY] )

New Business Won YTD =
    TOTALYTD ( [New Business Won], DimDate[date] )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01';
```

## 2. Deals won and average deal size

**Question.** How many contracts, how big?  
**Definition.** Count of signed contracts; average = won value / deals.  
**Grain.** opportunity · **Exclusions.** as above · **Owner.** Commercial Analytics  
**Differences between businesses.** Averages are not comparable across businesses (a CRO study vs an audit): always read by business.

DAX (measures in `_Measures`):

```dax
Deals Won =
    CALCULATE ( COUNTROWS ( FactOpportunity ), FactOpportunity[status] = "Won" )

Average Deal Size =
    DIVIDE ( [New Business Won], [Deals Won] )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(value_usd_governed) / COUNT(*) FROM fact WHERE status = 'Won' AND won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01';
```

## 3. Open pipeline

**Question.** What is still to be decided?  
**Definition.** Unweighted value of open opportunities at the data cut.  
**Grain.** opportunity (snapshot) · **Exclusions.** won, lost, disqualified; not filtered by date · **Owner.** Business sales ops  
**Differences between businesses.** CRO verbal awards are open until contracted. ADAMAS enquiries without quote are open.

DAX (measures in `_Measures`):

```dax
Open Pipeline =
    CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[status] = "Open", REMOVEFILTERS ( DimDate ) )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Open';
```

## 4. Weighted pipeline

**Question.** What can we expect from the pipeline?  
**Definition.** Open value x stage probability of the source system.  
**Grain.** opportunity (snapshot) · **Exclusions.** as open pipeline · **Owner.** Business sales ops (probabilities)  
**Differences between businesses.** Probabilities are each system's own (CRO CRM by stage; PV and ADAMAS set in src/prepare.py). To be harmonised: open item.

DAX (measures in `_Measures`):

```dax
Weighted Pipeline =
    CALCULATE ( SUM ( FactOpportunity[weighted_value_usd] ), FactOpportunity[status] = "Open", REMOVEFILTERS ( DimDate ) )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(weighted_value_usd) FROM fact WHERE status = 'Open';
```

## 5. Win rate (count)

**Question.** Of the deals we proposed on and that were decided, how many did we win?  
**Definition.** Won / (won + lost after a proposal), by decision date.  
**Grain.** decided opportunity x decision date · **Exclusions.** no bid, disqualified, lost before proposal · **Owner.** Commercial Analytics  
**Differences between businesses.** Without the stage mapping, 'Awarded' (CRO) and 'Signed' (PV) look alike: the group rate is wrong. See stage_map.csv.

DAX (measures in `_Measures`):

```dax
Decisions =
    CALCULATE ( COUNTROWS ( FactOpportunity ), FactOpportunity[in_win_rate] = TRUE (), USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) )

Win Rate =
    DIVIDE ( CALCULATE ( COUNTROWS ( FactOpportunity ), FactOpportunity[in_win_rate] = TRUE (), FactOpportunity[status] = "Won", USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ), [Decisions] )

Win Rate PY =
    CALCULATE ( [Win Rate], SAMEPERIODLASTYEAR ( DimDate[date] ) )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT AVG(CASE WHEN status = 'Won' THEN 1.0 ELSE 0 END) FROM fact WHERE in_win_rate AND decision_date >= DATE '2026-01-01' AND decision_date < DATE '2026-11-01';
```

## 6. Win rate (value)

**Question.** Same, weighted by value  
**Definition.** Won value / value of all decisions.  
**Grain.** decided opportunity · **Exclusions.** as above · **Owner.** Commercial Analytics  
**Differences between businesses.** Large CRO studies dominate: always show next to the count rate.

DAX (measures in `_Measures`):

```dax
Win Rate (value) =
    DIVIDE ( CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[in_win_rate] = TRUE (), FactOpportunity[status] = "Won", USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ), CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[in_win_rate] = TRUE (), USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ) )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(CASE WHEN status = 'Won' THEN value_usd_governed END) / SUM(value_usd_governed) FROM fact WHERE in_win_rate AND decision_date >= DATE '2026-01-01' AND decision_date < DATE '2026-11-01';
```

## 7. Proposal conversion (funnel)

**Question.** How many new opportunities reach a proposal?  
**Definition.** Share of opportunities created in the period that reached the proposal stage.  
**Grain.** opportunity x creation date (cohort) · **Exclusions.** none · **Owner.** Commercial Analytics  
**Differences between businesses.** Recent cohorts are immature (proposal not yet due): compare cohorts of the same age.

DAX (measures in `_Measures`):

```dax
Opportunities Created =
    CALCULATE ( COUNTROWS ( FactOpportunity ), USERELATIONSHIP ( FactOpportunity[created_date], DimDate[date] ) )

Reached Proposal % =
    DIVIDE ( CALCULATE ( COUNTROWS ( FactOpportunity ), FactOpportunity[reached_proposal] = TRUE (), USERELATIONSHIP ( FactOpportunity[created_date], DimDate[date] ) ), [Opportunities Created] )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT AVG(CASE WHEN reached_proposal THEN 1.0 ELSE 0 END) FROM fact WHERE created_date >= DATE '2026-01-01' AND created_date < DATE '2026-11-01';
```

## 8. Sales cycle (days)

**Question.** How long from first contact to signature?  
**Definition.** Average days from creation to signature, won deals.  
**Grain.** won opportunity · **Exclusions.** open and lost deals · **Owner.** Commercial Analytics  
**Differences between businesses.** CRO starts at the RFI; PV at the lead; ADAMAS at the enquiry: not the same starting event.

DAX (measures in `_Measures`):

```dax
Sales Cycle (days) =
    CALCULATE ( AVERAGE ( FactOpportunity[cycle_days] ), FactOpportunity[status] = "Won" )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT AVG(cycle_days) FROM fact WHERE status = 'Won' AND won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01';
```

## 9. Book-to-bill

**Question.** Are we signing more than we deliver?  
**Definition.** New business won / revenue recognised, same period.  
**Grain.** business x month · **Exclusions.** none · **Owner.** FP&A (revenue) · Commercial Analytics  
**Differences between businesses.** Listed CROs define it differently (net vs gross awards, service vs total revenue): data/public/competitors.csv.

DAX (measures in `_Measures`):

```dax
Book-to-Bill =
    DIVIDE ( [New Business Won], [Revenue] )

Revenue =
    SUM ( FactRevenue[revenue_usd] )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT (SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01') / (SELECT SUM(revenue_usd) FROM revenue WHERE month >= DATE '2026-01-01' AND month < DATE '2026-11-01');
```

## 10. Order book

**Question.** How much contracted work is left to deliver?  
**Definition.** Opening order book + won - revenue - cancellations, monthly.  
**Grain.** business x month (closing) · **Exclusions.** none · **Owner.** FP&A  
**Differences between businesses.** PV order book = remaining contract value of recurring contracts.

DAX (measures in `_Measures`):

```dax
Order Book =
    VAR m = MAX ( OrderBook[month] ) RETURN CALCULATE ( SUM ( OrderBook[closing_order_book] ), OrderBook[month] = m )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(closing_order_book) FROM orderbook WHERE month = DATE '2026-10-01';
```

## 11. Cancellation rate

**Question.** How much signed business is cancelled?  
**Definition.** Cancelled contract value / won value, same period.  
**Grain.** business x month · **Exclusions.** none · **Owner.** FP&A  
**Differences between businesses.** Only CRO contracts carry a cancellation date in the sources.

DAX (measures in `_Measures`):

```dax
Cancellation Rate =
    DIVIDE ( SUM ( OrderBook[cancelled] ), SUM ( OrderBook[won] ) )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT SUM(cancelled) / SUM(won) FROM orderbook WHERE month >= DATE '2026-01-01';
```

## 12. Attainment vs target

**Question.** Are we on plan?  
**Definition.** New business won / target. Re-phased target (quarter profile) and target as received (annual / 12).  
**Grain.** business x region x month · **Exclusions.** months not closed · **Owner.** FP&A (targets) · Commercial Analytics  
**Differences between businesses.** Flat monthly targets on a quarter-end business make mid-quarter months look behind: read QTD, not single months.

DAX (measures in `_Measures`):

```dax
Target =
    SUM ( FactTarget[target_phased_usd] )

Target (as received) =
    SUM ( FactTarget[target_flat_usd] )

Variance to Target =
    [New Business Won] - [Target]

Attainment % =
    DIVIDE ( [New Business Won], [Target] )

Attainment % (as received) =
    DIVIDE ( [New Business Won], [Target (as received)] )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT (SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01') / (SELECT SUM(target_phased_usd) FROM target WHERE month >= DATE '2026-01-01' AND month < DATE '2026-11-01');
```

## 13. Variance decomposition

**Question.** Why are we above / below last year?  
**Definition.** Won = decisions x win rate x average deal. Volume = (N1-N0) R0 A0; conversion = N1 (R1-R0) A0; deal size = N1 R1 (A1-A0). Exact.  
**Grain.** selection x decision date vs same period last year · **Exclusions.** as win rate · **Owner.** Commercial Analytics  
**Differences between businesses.** Order of substitution matters; we use volume, then conversion, then deal size, always the same.

DAX (measures in `_Measures`):

```dax
Volume Effect =
    VAR n1 = [Decisions] VAR n0 = CALCULATE ( [Decisions], SAMEPERIODLASTYEAR ( DimDate[date] ) ) VAR r0 = [Win Rate PY] VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) RETURN ( n1 - n0 ) * r0 * a0

Conversion Effect =
    VAR n1 = [Decisions] VAR r1 = [Win Rate] VAR r0 = [Win Rate PY] VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) RETURN n1 * ( r1 - r0 ) * a0

Deal Size Effect =
    VAR n1 = [Decisions] VAR r1 = [Win Rate] VAR a1 = [Avg Won Value (decision)] VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) RETURN n1 * r1 * ( a1 - a0 )

Avg Won Value (decision) =
    DIVIDE ( CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[in_win_rate] = TRUE (), FactOpportunity[status] = "Won", USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ), CALCULATE ( COUNTROWS ( FactOpportunity ), FactOpportunity[in_win_rate] = TRUE (), FactOpportunity[status] = "Won", USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ) )

Variance Bridge =
    SWITCH ( SELECTEDVALUE ( VarianceStep[step_sort] ), 1, CALCULATE ( CALCULATE ( SUM ( FactOpportunity[value_usd_governed] ), FactOpportunity[in_win_rate] = TRUE (), FactOpportunity[status] = "Won", USERELATIONSHIP ( FactOpportunity[decision_date], DimDate[date] ) ), SAMEPERIODLASTYEAR ( DimDate[date] ) ), 2, [Volume Effect], 3, [Conversion Effect], 4, [Deal Size Effect] )

```

## 14. Cross-sell share

**Question.** How much comes from clients of 2+ businesses?  
**Definition.** Share of new business won from clients that signed with at least two businesses.  
**Grain.** client · **Exclusions.** unmapped clients · **Owner.** Commercial Analytics  
**Differences between businesses.** Needs the group client id (clients_master.csv): each business has its own client codes.

DAX (measures in `_Measures`):

```dax
Cross-Sell Share =
    DIVIDE ( CALCULATE ( [New Business Won], DimClient[multi_business_client] = TRUE () ), [New Business Won] )

```

## 15. Data freshness and quality

**Question.** Can we trust this week's numbers?  
**Definition.** Late submissions (latest week), share of on-time submissions over 52 weeks, open quality checks.  
**Grain.** source x data owner x week · **Exclusions.** none · **Owner.** Commercial Operations  
**Differences between businesses.** Each data owner and deadline: REPORTING_CALENDAR.md.

DAX (measures in `_Measures`):

```dax
Late Sources =
    CALCULATE ( COUNTROWS ( DataHealth ), DataHealth[status] = "LATE" )

On-Time Rate (52 weeks) =
    AVERAGE ( DataHealth[on_time_rate_52w] )

Open DQ Issues =
    CALCULATE ( COUNTROWS ( DQIssues ), DQIssues[status] = "Open" )

```

SQL (DuckDB, `data/processed`):

```sql
SELECT COUNT(*) FROM health WHERE status = 'LATE';
```
