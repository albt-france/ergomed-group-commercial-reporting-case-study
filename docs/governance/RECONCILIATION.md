# Reconciliation

Three levels: (1) public figures of Ergomed Group seen in two places, (2) every source file vs the model, (3) the 'stack the files' answer vs the governed one. Plus the SQL vs Python check of the KPIs.

## 1. Public figures (PUBLIC DATA, Companies House filings)

Figures typed from the scanned filings with the PDF page (`src/extract_accounts.py`, arithmetic checked).

| ID | Check | Figure A | Figure B | Gap | Explanation | Status |
|---|---|---|---|---|---|---|
| R1 | Revenue FY2022, KPI table vs note 2 | GBP 145.3m (KPI table, AR2022 p.35) | GBP 145,262k (note 2, p.94) | 0.0 | Rounding only: same figure, millions vs thousands. | Reconciled |
| R2 | Order book roll-forward 2021 | Opening 193.0 + net awards 165.3 - revenue 118.6 = 239.7 | Closing order book 239.7 (AR2021 p.26) | 0.0 | Closes exactly: the published net awards are consistent with the order book and revenue. | Reconciled |
| R3 | Order book roll-forward 2020 | Opening 124.1 + net awards 117.8 - revenue 86.4 = 155.5 | Closing order book 193.0 (AR2020 p.12) | -37.5 | Gap of GBP 37.5m. Hypothesis (not confirmed in the filing): order books acquired with the two 2020 acquisitions and FX. Would need the acquired-backlog figure from the data owner. | Open - hypothesis |
| R4 | Revenue by region FY2021, highlights vs note | UK & EMEA 36.9 + Asia 7.2 (AR2021 p.7) | UK 14.2 + Rest of EMEA 22.6 + Rest of World 7.4 (AR2022 p.94) | -0.1 | Same total, different region boundaries: 'Asia' in the highlights vs 'Rest of World' in the note. | Reconciled - mapping |
| R5 | Region list 2019-2020 vs 2021+ | UK, REMEA, North America, Asia, Australia | UK, REMEA, North America, Rest of World | 0.0 | Taxonomy change: Asia + Australia merged into Rest of World. Mapping table needed for a time series. | Reconciled - mapping |
| R6 | Revenue prior period (to Dec 2024), note 2 total vs its rows | Printed total 244,725 (TC2025 p.32) | Rows and income statement: 117,475 + 126,800 = 244,275 (TC2025 p.20) | 450.0 | Transposed digits in the printed total of the note; rows, the income statement and the narrative (USD 244.3m) agree on 244,275. | Reconciled - source typo |
| R7 | Comparability FY2023 -> FY2024 | FY2023: GBP, 12 months, Ergomed Group consolidated | FY2024: USD, 13.5 months of Ergomed results, Eden TopCo consolidated |  | Currency, period length and reporting entity all change. Not comparable without restating; growth rates across this break are not computed. | Documented |
| R8 | CRO service fee revenue FY2022 | GBP 50.8m (AR2022 p.36) | CRO revenue 71,363 - reimbursable expenses 20,647 = 50,716 (p.96) | 0.08 | GBP 0.1m. Hypothesis: service fee = revenue minus reimbursable *revenue*, which the notes do not show separately from reimbursable *expenses*. Small, left open. | Open - small |

## 2. Source files vs model (SIMULATED)

| Source | Check | Source | Model | Difference | Status | Note |
|---|---|---|---|---|---|---|
| cro_crm.xlsx | Rows | 1,169 | 1,168 | -1 | Explained | 1 duplicate excluded |
| cro_crm.xlsx | Amount, EUR (all records) | 1,305,673,000 | 1,302,356,000 | -3,317,000 | Explained | duplicate excluded |
| pv_pipeline.csv (+ NA late file) | Rows | 1,315 | 1,315 | 0 | OK | late NA file replaces the NA rows |
| pv_pipeline.csv (+ NA late file) | TCV, USD | 1,287,835,000 | 1,287,835,000 | 0 | OK |  |
| adamas_tracker.xlsx | Audit rows (excl. banners) | 1,633 | 1,633 | 0 | OK | month banner rows dropped |
| All | Won value USD: before vs after cross-sell rule | 755,063,670 | 744,818,670 | -10,245,000 | Explained | 7 cross-sell pairs: PV scope counted once |
| revenue_actuals.csv | Revenue USD | 543,439,300 | 543,439,300 | 0 | OK | finance file loaded as is |

## 3. Naive vs governed new business, Jan-Oct 2026

| Step | USD m | Note |
|---|---|---|
| Naive: stack the three files | 265.2 | sum of value columns, EUR + USD + GBP, 'Awarded' counted as won, duplicate included |
| Convert EUR and GBP to USD | 21.5 | ECB monthly average of the win month |
| Remove the duplicate CRM record | -3.9 | planted issue 4 |
| Won = signed contract, not verbal award | -22.1 | CRO 'Awarded' -> open; won dated at signature |
| Count cross-sell PV scope once | -4.6 | planted issue 1 |
| Governed: new business won, Jan-Oct 2026 | 256.0 | model value |

## 4. KPIs: SQL (DuckDB) vs Python

| KPI | SQL | Python | Match |
|---|---|---|---|
| New business won (net awards) | $255.96m | $255.96m | yes |
| Deals won and average deal size | $0.46m | - | - |
| Open pipeline | $246.56m | $246.56m | yes |
| Weighted pipeline | $75.54m | $75.54m | yes |
| Win rate (count) | 48.4% | 48.4% | yes |
| Win rate (value) | 32.9% | - | - |
| Proposal conversion (funnel) | 81.0% | - | - |
| Sales cycle (days) | 60.0 | - | - |
| Book-to-bill | 1.086x | 1.086x | yes |
| Order book | $498.48m | $498.48m | yes |
| Cancellation rate | 1.8% | - | - |
| Attainment vs target | 95.2% | 95.2% | yes |
| Variance decomposition | - | - | - |
| Cross-sell share | - | 66.4% | - |
| Data freshness and quality | 1.0 | 1.0 | yes |

Rule: a check that does not match stops the monthly pack until it is explained (owner and reason written here).
