# Reporting calendar, deadlines and refresh

## Weekly cycle (week = Monday to Sunday)
| When | What | Owner |
|---|---|---|
| Monday 10:00 | Deadline: CRM export, 3 PV regional trackers, ADAMAS tracker | each data owner |
| Monday 10:00-11:00 | Automatic refresh + quality checks (`src/prepare.py`, Power BI dataset refresh) | Commercial Analytics |
| Monday 12:00 | Weekly commercial report sent (`src/weekly_report.py`) | Commercial Analytics |

## Monthly cycle
| When | What | Owner |
|---|---|---|
| Working day 3 | Revenue and order book from finance (approved source) | FP&A |
| Working day 4 | Reconciliation (RECONCILIATION.md) signed off; open checks explained | Commercial Analytics |
| Working day 5 | Monthly commercial pack (`src/build_monthly_pack.py`), Group and business views | Commercial Analytics |

## If a source is late
1. Do not wait: the report goes out at 12:00, with a red **INCOMPLETE** banner naming the source, the owner and what is missing
   (the previous week's figures are used for that scope and shown as such).
2. Reminder to the owner at 10:15; escalation to the business lead at 14:00.
3. When the file arrives: refresh, restate, send a short correction with the difference (example: week 45, PV North America,
   received Wed 11 Nov 15:20: 4 signed deals, USD 5.8m, added in the restated version).
4. The on-time rate per owner is shown on the Data health page (52 weeks).

## Refresh (Power BI service)
- **Schedule**: dataset refresh Monday 10:30 and daily 06:00 (Pro: up to 8 a day). Sources are files: in production they live in
  a SharePoint / OneDrive folder (no gateway needed) or on a file share through the **on-premises data gateway** (standard mode,
  a service account with read access; gateway cluster of 2 machines for resilience).
- **Parameter**: `DataFolder` points to the folder of processed files; changing environment = changing one parameter.
- **If the refresh fails**: the service keeps the last good data and emails the dataset owner. Check (1) gateway online and
  credentials valid, (2) a file renamed or a column changed (the M step `Selected` fails on a missing column: by design), (3) a
  quality check that stops the pipeline. The weekly report is not sent on stale data: it states the last refresh time.
- **Row-level security**: roles `Group leadership` (all) and `Scoped user (business x region)` (dynamic, `SecUserScope`);
  users are assigned to roles in the service, tested with *View as* in Desktop (see powerbi/POWERBI_STEPS.md).
- **Performance**: import mode, ~4k opportunities; star schema, single-direction relationships, measures only (no calculated
  columns in DAX), integer keys where possible. Performance analyzer target: every visual < 500 ms.
- **Accessibility**: colour is never the only signal (labels on bars, red/green also in text), 10 pt minimum, tab order follows
  the reading order, alt text on charts in the service.
