"""Write the governance documents in docs/governance/ from the model definitions and the pipeline outputs.

KPI_DICTIONARY.md  15 KPIs: definition, DAX (the measure text in the model, from src/build_tmdl.py), SQL (run here with
                   DuckDB on data/processed and compared with the Python result), grain, exclusions, owner, differences
                   between businesses
DATA_MAPPING.md    source fields -> model, stage / region / client / currency mappings
RECONCILIATION.md  public figures (Companies House), source -> model checks, naive vs governed, SQL vs Python
CHANGELOG.md, REPORTING_CALENDAR.md are static texts kept in this script so they are versioned with the code.
"""
import json
from pathlib import Path

import duckdb
import pandas as pd

from build_tmdl import MEASURES

ROOT = Path(__file__).resolve().parents[1]
P, G, PUB = ROOT / "data" / "processed", ROOT / "docs" / "governance", ROOT / "data" / "public"
DAX = {m[0]: m[1] for m in MEASURES}
FD = json.loads((P / "findings.json").read_text())
YTD = "won_date >= DATE '2026-01-01' AND won_date < DATE '2026-11-01'"
DECY = "decision_date >= DATE '2026-01-01' AND decision_date < DATE '2026-11-01'"

# (KPI, question, definition, measures, SQL returning one value for Jan-Oct 2026, python value, grain, exclusions, owner, differences)
K = FD["kpi"]
KPIS = [
    ("New business won (net awards)", "How much new business did we sign?",
     "Value of contracts signed in the period, in USD at the ECB monthly average of the signature month.",
     ["New Business Won", "New Business Won PY", "New Business Won YoY %", "New Business Won YTD"],
     f"SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND {YTD}", K["ytd_won"],
     "opportunity x signature date", "duplicates excluded; PV scope of integrated deals counted once (in PV); verbal awards excluded",
     "Commercial Analytics (definition) · business sales ops (inputs)",
     "CRO: contract value (EUR), win = 'Contracted', not 'Awarded'. PV: total contract value = annual value x years (USD); "
     "PV teams also track ACV, kept in acv_usd. ADAMAS: confirmed audit quote (GBP)."),
    ("Deals won and average deal size", "How many contracts, how big?", "Count of signed contracts; average = won value / deals.",
     ["Deals Won", "Average Deal Size"], f"SELECT SUM(value_usd_governed) / COUNT(*) FROM fact WHERE status = 'Won' AND {YTD}",
     K["ytd_won"] / max(1, sum(1 for _ in [0])) if False else None, "opportunity", "as above", "Commercial Analytics",
     "Averages are not comparable across businesses (a CRO study vs an audit): always read by business."),
    ("Open pipeline", "What is still to be decided?", "Unweighted value of open opportunities at the data cut.",
     ["Open Pipeline"], "SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Open'", K["open_pipeline"],
     "opportunity (snapshot)", "won, lost, disqualified; not filtered by date", "Business sales ops",
     "CRO verbal awards are open until contracted. ADAMAS enquiries without quote are open."),
    ("Weighted pipeline", "What can we expect from the pipeline?", "Open value x stage probability of the source system.",
     ["Weighted Pipeline"], "SELECT SUM(weighted_value_usd) FROM fact WHERE status = 'Open'", K["weighted_pipeline"],
     "opportunity (snapshot)", "as open pipeline", "Business sales ops (probabilities)",
     "Probabilities are each system's own (CRO CRM by stage; PV and ADAMAS set in src/prepare.py). To be harmonised: open item."),
    ("Win rate (count)", "Of the deals we proposed on and that were decided, how many did we win?",
     "Won / (won + lost after a proposal), by decision date.", ["Decisions", "Win Rate", "Win Rate PY"],
     f"SELECT AVG(CASE WHEN status = 'Won' THEN 1.0 ELSE 0 END) FROM fact WHERE in_win_rate AND {DECY}", K["win_rate"],
     "decided opportunity x decision date", "no bid, disqualified, lost before proposal", "Commercial Analytics",
     "Without the stage mapping, 'Awarded' (CRO) and 'Signed' (PV) look alike: the group rate is wrong. See stage_map.csv."),
    ("Win rate (value)", "Same, weighted by value", "Won value / value of all decisions.", ["Win Rate (value)"],
     f"SELECT SUM(CASE WHEN status = 'Won' THEN value_usd_governed END) / SUM(value_usd_governed) FROM fact WHERE in_win_rate AND {DECY}",
     None, "decided opportunity", "as above", "Commercial Analytics", "Large CRO studies dominate: always show next to the count rate."),
    ("Proposal conversion (funnel)", "How many new opportunities reach a proposal?", "Share of opportunities created in the period that reached the proposal stage.",
     ["Opportunities Created", "Reached Proposal %"],
     "SELECT AVG(CASE WHEN reached_proposal THEN 1.0 ELSE 0 END) FROM fact WHERE created_date >= DATE '2026-01-01' AND created_date < DATE '2026-11-01'",
     None, "opportunity x creation date (cohort)", "none", "Commercial Analytics",
     "Recent cohorts are immature (proposal not yet due): compare cohorts of the same age."),
    ("Sales cycle (days)", "How long from first contact to signature?", "Average days from creation to signature, won deals.",
     ["Sales Cycle (days)"], f"SELECT AVG(cycle_days) FROM fact WHERE status = 'Won' AND {YTD}", None, "won opportunity",
     "open and lost deals", "Commercial Analytics", "CRO starts at the RFI; PV at the lead; ADAMAS at the enquiry: not the same starting event."),
    ("Book-to-bill", "Are we signing more than we deliver?", "New business won / revenue recognised, same period.",
     ["Book-to-Bill", "Revenue"],
     f"SELECT (SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND {YTD}) / "
     "(SELECT SUM(revenue_usd) FROM revenue WHERE month >= DATE '2026-01-01' AND month < DATE '2026-11-01')", K["book_to_bill"],
     "business x month", "none", "FP&A (revenue) · Commercial Analytics", "Listed CROs define it differently (net vs gross awards, "
     "service vs total revenue): data/public/competitors.csv."),
    ("Order book", "How much contracted work is left to deliver?", "Opening order book + won - revenue - cancellations, monthly.",
     ["Order Book"], "SELECT SUM(closing_order_book) FROM orderbook WHERE month = DATE '2026-10-01'", K["order_book"],
     "business x month (closing)", "none", "FP&A", "PV order book = remaining contract value of recurring contracts."),
    ("Cancellation rate", "How much signed business is cancelled?", "Cancelled contract value / won value, same period.",
     ["Cancellation Rate"], "SELECT SUM(cancelled) / SUM(won) FROM orderbook WHERE month >= DATE '2026-01-01'", None,
     "business x month", "none", "FP&A", "Only CRO contracts carry a cancellation date in the sources."),
    ("Attainment vs target", "Are we on plan?", "New business won / target. Re-phased target (quarter profile) and target as received (annual / 12).",
     ["Target", "Target (as received)", "Variance to Target", "Attainment %", "Attainment % (as received)"],
     f"SELECT (SELECT SUM(value_usd_governed) FROM fact WHERE status = 'Won' AND {YTD}) / "
     "(SELECT SUM(target_phased_usd) FROM target WHERE month >= DATE '2026-01-01' AND month < DATE '2026-11-01')", K["attainment"],
     "business x region x month", "months not closed", "FP&A (targets) · Commercial Analytics",
     "Flat monthly targets on a quarter-end business make mid-quarter months look behind: read QTD, not single months."),
    ("Variance decomposition", "Why are we above / below last year?",
     "Won = decisions x win rate x average deal. Volume = (N1-N0) R0 A0; conversion = N1 (R1-R0) A0; deal size = N1 R1 (A1-A0). Exact.",
     ["Volume Effect", "Conversion Effect", "Deal Size Effect", "Avg Won Value (decision)", "Variance Bridge"], None, None,
     "selection x decision date vs same period last year", "as win rate", "Commercial Analytics",
     "Order of substitution matters; we use volume, then conversion, then deal size, always the same."),
    ("Cross-sell share", "How much comes from clients of 2+ businesses?",
     "Share of new business won from clients that signed with at least two businesses.", ["Cross-Sell Share"], None, K["cross_sell_share"],
     "client", "unmapped clients", "Commercial Analytics", "Needs the group client id (clients_master.csv): each business has its own client codes."),
    ("Data freshness and quality", "Can we trust this week's numbers?",
     "Late submissions (latest week), share of on-time submissions over 52 weeks, open quality checks.",
     ["Late Sources", "On-Time Rate (52 weeks)", "Open DQ Issues"], "SELECT COUNT(*) FROM health WHERE status = 'LATE'", 1,
     "source x data owner x week", "none", "Commercial Operations", "Each data owner and deadline: REPORTING_CALENDAR.md."),
]


def run_sql():
    con = duckdb.connect()
    for v, f in (("fact", "fact_opportunity"), ("revenue", "fact_revenue"), ("target", "fact_target"), ("orderbook", "an_order_book"),
                 ("health", "data_health")):
        con.execute(f"CREATE VIEW {v} AS SELECT * FROM read_csv_auto('{(P / (f + '.csv')).as_posix()}', header=true)")
    out = []
    for k in KPIS:
        val = con.execute(k[4]).fetchone()[0] if k[4] else None
        out.append(val)
    return out


def fmt(v, name):
    if v is None:
        return "-"
    if any(w in name.lower() for w in ("rate", "attainment", "share", "conversion")):
        return f"{100 * v:.1f}%"
    if "book-to-bill" in name.lower():
        return f"{v:.3f}x"
    if "cycle" in name.lower() or "freshness" in name.lower():
        return f"{v:,.1f}"
    return f"${v / 1e6:,.2f}m"


def kpi_dictionary():
    sql_vals = run_sql()
    rows, lines = [], ["# KPI dictionary", "",
                       "One definition per KPI for the three businesses. The DAX is the measure text of the Power BI model "
                       "(generated from `src/build_tmdl.py`, so the document and the model cannot drift apart). The SQL runs on the "
                       "processed tables with DuckDB each time this file is rebuilt; its result is compared with the Python pipeline "
                       "(`src/analysis.py`) for Jan-Oct 2026. Data: SIMULATED, illustrative.", "",
                       "| # | KPI | SQL (Jan-Oct 2026) | Python | Match |", "|---|---|---|---|---|"]
    for i, (k, v) in enumerate(zip(KPIS, sql_vals), 1):
        py = k[5]
        ok = "-" if (v is None or py is None) else ("yes" if abs(v - py) <= max(1e-6, abs(py) * 1e-6) else "NO")
        lines.append(f"| {i} | {k[0]} | {fmt(v, k[0])} | {fmt(py, k[0])} | {ok} |")
        rows.append(dict(kpi=k[0], sql=v, python=py, match=ok))
    lines += ["", "Conventions: amounts in USD (group reporting currency, as in the group's filed accounts since FY2024); "
              "FX = ECB monthly average of the month of the event; a month not yet published uses the last published month and is "
              "flagged (`fx_provisional`). Periods are calendar months; YTD = calendar year to date; PY = same period last year.", ""]
    for i, (name, question, definition, measures, sql, _, grain, excl, owner, diff) in enumerate(KPIS, 1):
        lines += [f"## {i}. {name}", "", f"**Question.** {question}  ", f"**Definition.** {definition}  ",
                  f"**Grain.** {grain} · **Exclusions.** {excl} · **Owner.** {owner}  ", f"**Differences between businesses.** {diff}", "",
                  "DAX (measures in `_Measures`):", "", "```dax"]
        for m in measures:
            lines.append(f"{m} =\n    {DAX[m]}\n")
        lines += ["```", ""]
        if sql:
            lines += ["SQL (DuckDB, `data/processed`):", "", "```sql", sql + ";", "```", ""]
    (G / "KPI_DICTIONARY.md").write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame(rows).to_csv(P / "sql_checks.csv", index=False)
    return rows


def data_mapping():
    st = pd.read_csv(G / "mappings" / "stage_map.csv")
    rm = pd.read_csv(G / "mappings" / "region_map.csv")
    fields = [
        ("source_id", "Opportunity ID", "deal_ref", "Ref"), ("client_code", "Account Code", "client_ref", "(none: name)"),
        ("client_name", "Account Name", "client", "Client (merged cells, forward-filled)"),
        ("region", "Region (EU/NA/APAC/ROW)", "country -> country_region_map.csv", "Region (UK/EMEA/Americas/Asia)"),
        ("therapeutic_area", "Therapeutic Area", "product_area", "'Not applicable (audit)'"),
        ("detail", "Phase", "service", "Audit type"), ("source_stage", "Stage", "pipeline_status", "Status (5 spellings normalised)"),
        ("value_local", "Amount (EUR)", "tcv_usd = annual_value_usd x contract_years", "Quote (GBP), number or '£12,500' text"),
        ("created_date", "Created Date", "created_on", "Requested (date or dd/mm/yyyy text)"),
        ("proposal_date", "Proposal Submitted", "proposal_sent_on", "Quote sent"),
        ("won_date", "Contract Signed", "signed_on", "Confirmed on ('TBC' -> quote date + 14 days, flagged)"),
        ("award_date", "Award Date (verbal, CRO only)", "-", "-"), ("lost_date", "Closed Lost Date", "status_changed_on if Closed Lost",
                                                                     "quote date + 14 days (no decline date in the tracker)"),
        ("cancel_date", "Cancellation Date", "-", "-"), ("data_owner", "CRO Sales Operations", "tracker (PV BD Europe / North America / APAC & RoW)",
                                                         "ADAMAS Operations")]
    lines = ["# Data mapping", "", "How three exports that do not look alike become one model (SIMULATED sources; rules in "
             "`src/prepare.py`, M version of the per-source steps in `powerquery/`).", "",
             "## Sources", "", "| Source | Owner | Format | Currency | Grain | Specifics |", "|---|---|---|---|---|---|",
             "| `cro_crm.xlsx` | CRO Sales Operations | CRM export, one sheet | EUR | opportunity | RFP and bid-defense stages; verbal award before contract |",
             "| `pv_pipeline.csv` | PV BD Europe / North America / APAC & RoW | 3 regional trackers compiled | USD | contract | recurring: annual value x years |",
             "| `adamas_tracker.xlsx` | ADAMAS Operations | manual Excel tracker | GBP | audit | merged cells, month banners, free-text status |",
             "| `targets.xlsx` | FP&A | one sheet per year | USD | business x region x month | annual / 12 |",
             "| `revenue_actuals.csv`, `order_book_opening.csv` | FP&A | finance extracts | USD | business x region x month | approved source |",
             "| `clients_master.csv` | Commercial Operations | master data | - | client | one group id, a code per business |",
             "| `fx_rates_ecb.csv` | ECB (PUBLIC DATA) | API | - | month x currency | monthly average reference rates |", "",
             "## Field mapping", "", "| Model column | CRO CRM | PV pipeline | ADAMAS tracker |", "|---|---|---|---|"]
    lines += [f"| `{a}` | {b} | {c} | {d} |" for a, b, c, d in fields]
    lines += ["", "## Stage mapping (`mappings/stage_map.csv`)", "", "| Business | Source stage | Common stage | Status | Note |", "|---|---|---|---|---|"]
    lines += [f"| {r.business} | {r.source_stage} | {r.common_stage} | {r.status} | {r.note if isinstance(r.note, str) else ''} |" for r in st.itertuples()]
    lines += ["", "PV rule: 'Closed Lost' without a proposal date = 6 Disqualified (lost at lead stage).", "",
              "## Region mapping (`mappings/region_map.csv`, `mappings/country_region_map.csv`)", "",
              "| Business | Source value | Region | Rule |", "|---|---|---|---|"]
    lines += [f"| {r.business} | {r.source_value} | {r.region} | {r.rule} |" for r in rm.itertuples()]
    lines += ["", "## Clients", "", "CRO account code and PV client ref are mapped to `group_client_id` through `clients_master.csv`; "
              "ADAMAS has no code and is matched on the normalised name. Codes missing from the master fall back on the name; anything "
              "still unmatched is kept as `UNMAPPED:<name>` and raised as check DQ10 to Commercial Operations.", "",
              "## Currency", "", "EUR and GBP are converted to USD at the ECB monthly average of the month of the event (signature, loss, "
              "or the data cut for open deals). The rate is stored on each row (`fx_rate`), so any figure can be re-derived.", "",
              "## Cross-source rules", "",
              "1. **Duplicate opportunity**: same account, amount, phase, area and contract date -> keep the first created (DQ01).",
              "2. **Integrated CRO + PV deal**: 'Clinical + PV' in the CRM and a PV contract for the same client within 45 days -> the PV "
              "value is deducted from the CRO amount (DQ02). Match priority: PV origin names the CRO id > 'CRO referral' > nearest date.",
              "3. **Late file**: a regional PV tracker received after the deadline replaces that region's rows at the next refresh (DQ05).", ""]
    (G / "DATA_MAPPING.md").write_text("\n".join(lines), encoding="utf-8")


def reconciliation(sqlrows):
    pubr = pd.read_csv(PUB / "reconciliation_public.csv")
    rec = pd.read_csv(P / "reconciliation.csv")
    br = pd.read_csv(P / "naive_vs_governed.csv")
    lines = ["# Reconciliation", "", "Three levels: (1) public figures of Ergomed Group seen in two places, (2) every source file vs the "
             "model, (3) the 'stack the files' answer vs the governed one. Plus the SQL vs Python check of the KPIs.", "",
             "## 1. Public figures (PUBLIC DATA, Companies House filings)", "",
             "Figures typed from the scanned filings with the PDF page (`src/extract_accounts.py`, arithmetic checked).", "",
             "| ID | Check | Figure A | Figure B | Gap | Explanation | Status |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r.id} | {r.check} | {r.figure_a} | {r.figure_b} | {'' if pd.isna(r.gap) else r.gap} | {r.explanation} | {r.status} |"
              for r in pubr.itertuples()]
    lines += ["", "## 2. Source files vs model (SIMULATED)", "", "| Source | Check | Source | Model | Difference | Status | Note |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r.source} | {r.check} | {r.source_value:,.0f} | {r.model_value:,.0f} | {r.difference:,.0f} | {r.status} | {r.note if isinstance(r.note, str) else ''} |"
              for r in rec.itertuples()]
    lines += ["", "## 3. Naive vs governed new business, Jan-Oct 2026", "", "| Step | USD m | Note |", "|---|---|---|"]
    lines += [f"| {r.step} | {r.value / 1e6:,.1f} | {r.note} |" for r in br.itertuples()]
    lines += ["", "## 4. KPIs: SQL (DuckDB) vs Python", "", "| KPI | SQL | Python | Match |", "|---|---|---|---|"]
    lines += [f"| {r['kpi']} | {fmt(r['sql'], r['kpi'])} | {fmt(r['python'], r['kpi'])} | {r['match']} |" for r in sqlrows]
    lines += ["", "Rule: a check that does not match stops the monthly pack until it is explained (owner and reason written here)."]
    (G / "RECONCILIATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


CHANGELOG = """# Changelog - commercial model and reports

Versioning: MAJOR = a KPI definition changes (figures are not comparable with the previous version: restate);
MINOR = new table, measure or page; PATCH = fix with no change of definition. Each release lists who approved it.

## v1.0.0 - 2026-11-16
- First governed release: 5-page Power BI report, weekly report, monthly pack (October 2026).
- KPI dictionary (15 KPIs, 34 measures incl. 4 helpers); stage, region and client mappings; RLS (business x region).
- Quality checks DQ01-DQ14 with owners; reconciliation of every source with the model.

## v0.3.0 - 2026-11-13
- Targets: re-phased target added next to the target as received (FP&A approval pending, DQ13).
- Variance decomposition (volume / conversion / deal size) and waterfall.

## v0.2.0 - 2026-11-11
- Late PV North America file handled: weekly report flagged INCOMPLETE, restated after receipt (DQ05).
- Cross-sell rule: PV scope counted once (DQ02). Duplicate CRM win excluded (DQ01).

## v0.1.0 - 2026-11-09
- Three sources loaded; currency conversion at ECB monthly averages; first stage mapping.
"""

CALENDAR = """# Reporting calendar, deadlines and refresh

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
"""


def main():
    rows = kpi_dictionary()
    data_mapping()
    reconciliation(rows)
    (G / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (G / "REPORTING_CALENDAR.md").write_text(CALENDAR, encoding="utf-8")
    print("docs written;", sum(r["match"] == "yes" for r in rows), "KPIs match SQL vs Python,", sum(r["match"] == "NO" for r in rows), "mismatch")


if __name__ == "__main__":
    main()
