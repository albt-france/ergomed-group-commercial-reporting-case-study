"""Write the Power BI project: semantic model (TMDL) + project scaffolding for powerbi/ErgomedCommercial.pbip.

Star schema (SIMULATED commercial data + one PUBLIC table for the FX policy is in docs, not in the model)
  facts       FactOpportunity (one row per opportunity, all three businesses, governed USD values)
              FactTarget (business x region x month), FactRevenue (finance), OrderBook (monthly roll-forward)
  dimensions  DimDate (marked date table), DimBusiness, DimRegion, DimTherapeuticArea, DimClient, DimStage
  governance  StageMap, DataHealth, DQIssues, Reconciliation, NaiveBridge, SecUserScope (RLS), VarianceStep
Every table reads a CSV from the DataFolder parameter (default C:\\case-study-ergomed\\data\\processed\\).
Usage: python src/build_tmdl.py      (close Power BI Desktop first: the model files are rewritten)
The MEASURES list is also the source of the DAX printed in docs/governance/KPI_DICTIONARY.md (src/build_docs.py).
"""
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAME = "ErgomedCommercial"
SM = PBI / f"{NAME}.SemanticModel"
DEF = SM / "definition"
DATA_FOLDER = "C:\\case-study-ergomed\\data\\processed\\"


def tag(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ergomed-commercial/" + "/".join(parts)))


def q(name):
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


M_TYPE = {"int": "Int64.Type", "num": "type number", "text": "type text", "bool": "type logical", "date": "type date"}
TMDL_TYPE = {"int": "int64", "num": "double", "text": "string", "bool": "boolean", "date": "dateTime"}
USD, USDM, PCT, PCT1, INT, X2 = '\\$#,0', '\\$#,0.0,,"m"', "0%", "0.0%", "#,0", '0.00"x"'


def T(name, path, cols, hidden=(), sort=None, desc="", date_table=False, hide_table=False):
    return dict(name=name, path=path, cols=cols, hidden=set(hidden), sort=sort or {}, desc=desc, date=date_table, hide=hide_table)


C = lambda *a: a  # noqa: E731  (column spec: name, kind, format)

TABLES = [
    T("FactOpportunity", "fact_opportunity.csv", [
        C("opp_key", "int", "0"), C("business", "text"), C("source_id", "text"), C("group_client_id", "text"),
        C("client_name", "text"), C("region", "text"), C("country", "text"), C("therapeutic_area", "text"), C("detail", "text"),
        C("services", "text"), C("source_stage", "text"), C("common_stage", "text"), C("status", "text"), C("currency", "text"),
        C("value_local", "num", INT), C("fx_rate", "num", "0.0000"), C("fx_provisional", "bool"), C("value_usd", "num", USD),
        C("cross_sell_adj_usd", "num", USD), C("value_usd_governed", "num", USD), C("acv_usd", "num", USD),
        C("probability", "num", PCT), C("weighted_value_usd", "num", USD), C("created_date", "date"), C("proposal_date", "date"),
        C("award_date", "date"), C("won_date", "date"), C("lost_date", "date"), C("decision_date", "date"), C("cancel_date", "date"),
        C("reached_proposal", "bool"), C("in_win_rate", "bool"), C("cycle_days", "num", "0"), C("is_cross_sell", "bool"),
        C("verbal_award_open", "bool"), C("loss_reason", "text"), C("data_owner", "text")],
      hidden=["opp_key"], desc="SIMULATED. One row per opportunity of the three businesses, harmonised by src/prepare.py: "
                                "common stage, USD at the ECB monthly average, group client id, duplicates excluded, cross-sell counted once."),
    T("FactTarget", "fact_target.csv", [C("business", "text"), C("region", "text"), C("month", "date"),
        C("target_flat_usd", "num", USD), C("target_phased_usd", "num", USD), C("fy_target_usd", "num", USD)],
      hidden=["fy_target_usd"], desc="SIMULATED. New-business targets: as received (annual / 12) and re-phased (month-in-quarter profile)."),
    T("FactRevenue", "fact_revenue.csv", [C("business", "text"), C("region", "text"), C("month", "date"), C("revenue_usd", "num", USD)],
      desc="SIMULATED. Recognised revenue from finance (approved source for book-to-bill)."),
    T("OrderBook", "an_order_book.csv", [C("business", "text"), C("month", "date"), C("won", "num", USD), C("revenue", "num", USD),
        C("cancelled", "num", USD), C("closing_order_book", "num", USD)],
      desc="SIMULATED. Monthly order-book roll-forward: opening + won - revenue - cancellations."),
    T("DimDate", "dim_date.csv", [C("date", "date"), C("year", "int", "0"), C("month_num", "int", "0"), C("month", "date"),
        C("month_label", "text"), C("quarter", "text"), C("week_ending", "date"), C("quarter_end_week", "bool"),
        C("is_closed_month", "bool")], hidden=["month_num"], sort={"month_label": "month"}, date_table=True),
    T("DimBusiness", "dim_business.csv", [C("business", "text"), C("business_sort", "int", "0"), C("source_currency", "text"),
        C("value_basis", "text"), C("won_definition", "text")], hidden=["business_sort"], sort={"business": "business_sort"}),
    T("DimRegion", "dim_region.csv", [C("region", "text"), C("region_sort", "int", "0")], hidden=["region_sort"], sort={"region": "region_sort"}),
    T("DimTherapeuticArea", "dim_therapeutic_area.csv", [C("therapeutic_area", "text"), C("ta_group", "text")]),
    T("DimClient", "dim_client.csv", [C("group_client_id", "text"), C("client_name", "text"), C("hq_region", "text"),
        C("size_segment", "text"), C("businesses_won", "int", "0"), C("multi_business_client", "bool")],
      desc="SIMULATED anonymous clients ('Sponsor 014'); one id across the three businesses."),
    T("DimStage", "dim_stage.csv", [C("common_stage", "text"), C("stage_order", "int", "0")], hidden=["stage_order"],
      sort={"common_stage": "stage_order"}),
    T("StageMap", "stage_map.csv", [C("business", "text"), C("source_stage", "text"), C("common_stage", "text"),
        C("stage_order", "int", "0"), C("status", "text"), C("note", "text")], desc="Governed mapping of each source stage to the common funnel."),
    T("DataHealth", "data_health.csv", [C("week_ending", "date"), C("source_file", "text"), C("data_owner", "text"), C("scope", "text"),
        C("deadline", "text"), C("received", "text"), C("on_time", "bool"), C("hours_late", "num", "0.0"), C("rows_in_model", "int", INT),
        C("on_time_rate_52w", "num", PCT), C("completeness", "num", PCT1), C("status", "text"), C("impact", "text")]),
    T("DQIssues", "dq_issues.csv", [C("check_id", "text"), C("check", "text"), C("source", "text"), C("data_owner", "text"),
        C("rows_flagged", "int", INT), C("severity", "text"), C("status", "text"), C("action", "text")]),
    T("Reconciliation", "reconciliation.csv", [C("source", "text"), C("check", "text"), C("source_value", "num", INT),
        C("model_value", "num", INT), C("difference", "num", INT), C("status", "text"), C("note", "text")]),
    T("NaiveBridge", "naive_vs_governed.csv", [C("step", "text"), C("value", "num", USDM), C("note", "text")]),
    T("SecUserScope", "sec_user_scope.csv", [C("user_principal_name", "text"), C("business", "text"), C("region", "text")],
      desc="SIMULATED RLS mapping (fictional @example.com accounts): user -> business x region.", hide_table=True),
]
STATIC = [("VarianceStep", [("step", "text"), ("step_sort", "int")],
           [("Last year", 1), ("Volume (decisions)", 2), ("Conversion (win rate)", 3), ("Deal size", 4)], {"step": "step_sort"})]

RELATIONSHIPS = [  # from table, from column, to table, to column, active
    ("FactOpportunity", "won_date", "DimDate", "date", True),
    ("FactOpportunity", "decision_date", "DimDate", "date", False),
    ("FactOpportunity", "created_date", "DimDate", "date", False),
    ("FactOpportunity", "business", "DimBusiness", "business", True),
    ("FactOpportunity", "region", "DimRegion", "region", True),
    ("FactOpportunity", "therapeutic_area", "DimTherapeuticArea", "therapeutic_area", True),
    ("FactOpportunity", "group_client_id", "DimClient", "group_client_id", True),
    ("FactOpportunity", "common_stage", "DimStage", "common_stage", True),
    ("FactTarget", "month", "DimDate", "date", True), ("FactTarget", "business", "DimBusiness", "business", True),
    ("FactTarget", "region", "DimRegion", "region", True),
    ("FactRevenue", "month", "DimDate", "date", True), ("FactRevenue", "business", "DimBusiness", "business", True),
    ("FactRevenue", "region", "DimRegion", "region", True),
    ("OrderBook", "month", "DimDate", "date", True), ("OrderBook", "business", "DimBusiness", "business", True),
]

# ---------------------------------------------------------------- measures (name, DAX, format, folder, description)
F = "FactOpportunity"
DEC = f"USERELATIONSHIP ( {F}[decision_date], DimDate[date] )"
CRE = f"USERELATIONSHIP ( {F}[created_date], DimDate[date] )"
WONF = f'{F}[status] = "Won"'
MEASURES = [
    ("New Business Won", f"CALCULATE ( SUM ( {F}[value_usd_governed] ), {WONF} )", USD, "1 Wins",
     "Value of contracts signed in the period (won date), USD, duplicates excluded, cross-sell PV scope counted once."),
    ("Deals Won", f"CALCULATE ( COUNTROWS ( {F} ), {WONF} )", INT, "1 Wins", "Number of contracts signed in the period."),
    ("Average Deal Size", "DIVIDE ( [New Business Won], [Deals Won] )", USD, "1 Wins", "New business won / deals won."),
    ("New Business Won PY", "CALCULATE ( [New Business Won], SAMEPERIODLASTYEAR ( DimDate[date] ) )", USD, "1 Wins",
     "Same period last year."),
    ("New Business Won YoY %", "DIVIDE ( [New Business Won] - [New Business Won PY], [New Business Won PY] )", PCT, "1 Wins", ""),
    ("New Business Won YTD", "TOTALYTD ( [New Business Won], DimDate[date] )", USD, "1 Wins", "Calendar year to date."),
    ("Cross-Sell Share", "DIVIDE ( CALCULATE ( [New Business Won], DimClient[multi_business_client] = TRUE () ), [New Business Won] )",
     PCT, "1 Wins", "Share of new business won from clients that signed with 2+ businesses."),
    ("Open Pipeline", f'CALCULATE ( SUM ( {F}[value_usd_governed] ), {F}[status] = "Open", REMOVEFILTERS ( DimDate ) )', USD,
     "2 Pipeline", "Unweighted value of open opportunities at the data cut (not time-filtered)."),
    ("Weighted Pipeline", f'CALCULATE ( SUM ( {F}[weighted_value_usd] ), {F}[status] = "Open", REMOVEFILTERS ( DimDate ) )', USD,
     "2 Pipeline", "Open value x stage probability of the source system."),
    ("Opportunities Created", f"CALCULATE ( COUNTROWS ( {F} ), {CRE} )", INT, "2 Pipeline", "Opportunities created in the period."),
    ("Reached Proposal %", f"DIVIDE ( CALCULATE ( COUNTROWS ( {F} ), {F}[reached_proposal] = TRUE (), {CRE} ), [Opportunities Created] )",
     PCT, "2 Pipeline", "Share of opportunities created in the period that reached the proposal stage (cohort)."),
    ("Verbal Awards Pending", f"CALCULATE ( COUNTROWS ( {F} ), {F}[verbal_award_open] = TRUE (), REMOVEFILTERS ( DimDate ) )", INT,
     "2 Pipeline", "CRO 'Awarded' without a signed contract: open, not won."),
    ("Decisions", f"CALCULATE ( COUNTROWS ( {F} ), {F}[in_win_rate] = TRUE (), {DEC} )", INT, "3 Conversion",
     "Opportunities won or lost after a proposal, by decision date."),
    ("Win Rate", f'DIVIDE ( CALCULATE ( COUNTROWS ( {F} ), {F}[in_win_rate] = TRUE (), {WONF}, {DEC} ), [Decisions] )', PCT, "3 Conversion",
     "Won / (won + lost after a proposal), by count."),
    ("Win Rate (value)", f'DIVIDE ( CALCULATE ( SUM ( {F}[value_usd_governed] ), {F}[in_win_rate] = TRUE (), {WONF}, {DEC} ), '
                         f'CALCULATE ( SUM ( {F}[value_usd_governed] ), {F}[in_win_rate] = TRUE (), {DEC} ) )', PCT, "3 Conversion",
     "Won value / value of all decisions."),
    ("Win Rate PY", "CALCULATE ( [Win Rate], SAMEPERIODLASTYEAR ( DimDate[date] ) )", PCT, "3 Conversion", ""),
    ("Sales Cycle (days)", f"CALCULATE ( AVERAGE ( {F}[cycle_days] ), {WONF} )", "0", "3 Conversion",
     "Average days from creation to signature, won deals."),
    ("Target", "SUM ( FactTarget[target_phased_usd] )", USD, "4 Targets", "Re-phased target (month-in-quarter profile)."),
    ("Target (as received)", "SUM ( FactTarget[target_flat_usd] )", USD, "4 Targets", "Target as received: annual / 12."),
    ("Variance to Target", "[New Business Won] - [Target]", USD, "4 Targets", ""),
    ("Attainment %", "DIVIDE ( [New Business Won], [Target] )", PCT, "4 Targets", "New business won / re-phased target."),
    ("Attainment % (as received)", "DIVIDE ( [New Business Won], [Target (as received)] )", PCT, "4 Targets", ""),
    ("Volume Effect", "VAR n1 = [Decisions] VAR n0 = CALCULATE ( [Decisions], SAMEPERIODLASTYEAR ( DimDate[date] ) ) "
                      "VAR r0 = [Win Rate PY] VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) "
                      "RETURN ( n1 - n0 ) * r0 * a0", USD, "5 Variance", "Change in decisions x last year's win rate x last year's deal size."),
    ("Conversion Effect", "VAR n1 = [Decisions] VAR r1 = [Win Rate] VAR r0 = [Win Rate PY] "
                          "VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) "
                          "RETURN n1 * ( r1 - r0 ) * a0", USD, "5 Variance", "This year's decisions x change in win rate x last year's deal size."),
    ("Deal Size Effect", "VAR n1 = [Decisions] VAR r1 = [Win Rate] VAR a1 = [Avg Won Value (decision)] "
                         "VAR a0 = CALCULATE ( [Avg Won Value (decision)], SAMEPERIODLASTYEAR ( DimDate[date] ) ) "
                         "RETURN n1 * r1 * ( a1 - a0 )", USD, "5 Variance", "This year's wins x change in average won value."),
    ("Avg Won Value (decision)", f"DIVIDE ( CALCULATE ( SUM ( {F}[value_usd_governed] ), {F}[in_win_rate] = TRUE (), {WONF}, {DEC} ), "
                                 f"CALCULATE ( COUNTROWS ( {F} ), {F}[in_win_rate] = TRUE (), {WONF}, {DEC} ) )", USD, "5 Variance",
     "Average won value by decision date (helper of the decomposition)."),
    ("Variance Bridge", "SWITCH ( SELECTEDVALUE ( VarianceStep[step_sort] ), "
                        f"1, CALCULATE ( CALCULATE ( SUM ( {F}[value_usd_governed] ), {F}[in_win_rate] = TRUE (), {WONF}, {DEC} ), SAMEPERIODLASTYEAR ( DimDate[date] ) ), "
                        "2, [Volume Effect], 3, [Conversion Effect], 4, [Deal Size Effect] )", USD, "5 Variance",
     "Waterfall: last year's won value, then the three effects; the visual's total = this year."),
    ("Revenue", "SUM ( FactRevenue[revenue_usd] )", USD, "6 Revenue & order book", "Recognised revenue (finance)."),
    ("Book-to-Bill", "DIVIDE ( [New Business Won], [Revenue] )", X2, "6 Revenue & order book", "New business won / revenue, same period."),
    ("Order Book", "VAR m = MAX ( OrderBook[month] ) RETURN CALCULATE ( SUM ( OrderBook[closing_order_book] ), OrderBook[month] = m )",
     USD, "6 Revenue & order book", "Closing order book of the last month in the period."),
    ("Cancellation Rate", "DIVIDE ( SUM ( OrderBook[cancelled] ), SUM ( OrderBook[won] ) )", PCT1, "6 Revenue & order book",
     "Cancelled contract value / won value, same period."),
    ("Late Sources", 'CALCULATE ( COUNTROWS ( DataHealth ), DataHealth[status] = "LATE" )', INT, "7 Data health",
     "Submissions received after the deadline (latest week)."),
    ("Open DQ Issues", 'CALCULATE ( COUNTROWS ( DQIssues ), DQIssues[status] = "Open" )', INT, "7 Data health", "Quality checks still open."),
    ("On-Time Rate (52 weeks)", "AVERAGE ( DataHealth[on_time_rate_52w] )", PCT, "7 Data health", "Share of weekly submissions on time."),
]

ROLES = [
    ("Group leadership", "All businesses and regions (executive view).", {}),
    ("Scoped user (business x region)", "Dynamic RLS: a signed-in user sees only the businesses and regions mapped to the account in SecUserScope.",
     {"DimBusiness": "[business] IN CALCULATETABLE ( VALUES ( SecUserScope[business] ), SecUserScope[user_principal_name] = USERPRINCIPALNAME () )",
      "DimRegion": "[region] IN CALCULATETABLE ( VALUES ( SecUserScope[region] ), SecUserScope[user_principal_name] = USERPRINCIPALNAME () )",
      "SecUserScope": "[user_principal_name] = USERPRINCIPALNAME ()"}),
    ("Business - Ergomed CRO (static)", "Static test role.", {"DimBusiness": '[business] = "Ergomed CRO"'}),
    ("Region - Europe (static)", "Static test role.", {"DimRegion": '[region] = "Europe"'}),
]


# ---------------------------------------------------------------- writers
def column_block(table, name, kind, fmt=None, hidden=False, sort_by=None, is_key=False):
    lines = [f"\tcolumn {q(name)}", f"\t\tdataType: {TMDL_TYPE[kind]}"]
    if is_key:
        lines.append("\t\tisKey")
    if hidden:
        lines.append("\t\tisHidden")
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if kind == "date" and not fmt:
        lines.append("\t\tformatString: yyyy-mm-dd")
    lines += [f"\t\tlineageTag: {tag(table, name)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}"]
    if sort_by:
        lines.append(f"\t\tsortByColumn: {sort_by}")
    if kind == "date":
        lines += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
    return "\n".join(lines) + "\n"


def m_block(lines):
    return "\n".join("\t\t\t\t" + l for l in lines)


def write_csv_table(t):
    name, cols = t["name"], t["cols"]
    out = ([f"/// {t['desc']}"] if t["desc"] else []) + [f"table {q(name)}", f"\tlineageTag: {tag(name)}"]
    if t["date"]:
        out.append("\tdataCategory: Time")
    if t["hide"]:
        out.append("\tisHidden")
    out.append("")
    for c in cols:
        c_name, kind, fmt = c[0], c[1], (c[2] if len(c) > 2 else None)
        out.append(column_block(name, c_name, kind, fmt, hidden=c_name in t["hidden"], sort_by=t["sort"].get(c_name),
                                is_key=t["date"] and c_name == "date"))
    types = ", ".join(f'{{"{c[0]}", {M_TYPE[c[1]]}}}' for c in cols)
    steps = [f'Source = Csv.Document(File.Contents(DataFolder & "{t["path"]}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
             "Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
             f"Selected = Table.SelectColumns(Promoted, {{{', '.join(json.dumps(c[0]) for c in cols)}}}),",
             "// empty CSV cells become null before typing (dates of open deals, missing ACV, ...)",
             "Blanks = Table.TransformColumns(Selected, List.Transform(Table.ColumnNames(Selected), each {_, each if _ = \"\" then null else _})),",
             f'Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")']
    out += [f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource =",
            m_block(["let"] + ["\t" + s for s in steps] + ["in", "\tTyped"]), ""]
    return "\n".join(out)


def write_static(name, cols, rows, sort_by):
    out = [f"table {q(name)}", f"\tlineageTag: {tag(name)}", ""]
    for c, kind in cols:
        out.append(column_block(name, c, kind, hidden=c.endswith("_sort"), sort_by=sort_by.get(c)))
    typ = ", ".join(f"{c} = {'Int64.Type' if k == 'int' else 'text'}" for c, k in cols)
    vals = ", ".join("{" + ", ".join(json.dumps(v) for v in r) + "}" for r in rows)
    out += [f"\tpartition {q(name)} = m", "\t\tmode: import", f"\t\tsource = #table(type table [{typ}], {{{vals}}})", ""]
    return "\n".join(out)


def write_measures():
    out = ["table _Measures", f"\tlineageTag: {tag('_Measures')}", ""]
    for name, dax, fmt, folder, desc in MEASURES:
        out += ([f"\t/// {desc}"] if desc else []) + [f"\tmeasure {q(name)} = {dax}", *([f"\t\tformatString: {fmt}"] if fmt else []),
                                                       f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {tag('_Measures', name)}", ""]
    out.append(column_block("_Measures", "_", "text", hidden=True))
    out += ["\tpartition _Measures = m", "\t\tmode: import", "\t\tsource = #table(type table [_ = text], {})", ""]
    return "\n".join(out)


def write_role(name, desc, perms):
    out = [f"/// {desc}", f"role {q(name)}", "\tmodelPermission: read", ""]
    for table, expr in perms.items():
        out += [f"\ttablePermission {q(table)} = {expr}", ""]
    out.append(f"\tannotation PBI_Id = {uuid.uuid5(uuid.NAMESPACE_URL, 'role/' + name).hex}")
    return "\n".join(out) + "\n"


def platform(kind, display):
    return json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                       "metadata": {"type": kind, "displayName": display},
                       "config": {"version": "2.0", "logicalId": tag("platform", kind)}}, indent=2)


def scaffold():
    """.pbip, report scaffolding and theme (copied from the house theme in powerbi/theme.json)."""
    (PBI / f"{NAME}.pbip").write_text(json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                                  "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    rep = PBI / f"{NAME}.Report"
    (rep / "definition").mkdir(parents=True, exist_ok=True)
    (rep / ".platform").write_text(platform("Report", NAME), encoding="utf-8")
    (rep / "definition.pbir").write_text(json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}},
                                                    indent=2), encoding="utf-8")
    (SM / ".platform").write_text(platform("SemanticModel", NAME), encoding="utf-8")
    (SM / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    theme = json.loads((PBI / "theme.json").read_text(encoding="utf-8"))
    reg = rep / "StaticResources" / "RegisteredResources"
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "CaseStudy_Light.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")
    report = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
              "themeCollection": {"customTheme": {"name": "CaseStudy_Light.json",
                                                  "reportVersionAtImport": {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"},
                                                  "type": "RegisteredResources"}},
              "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
              "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                                    "items": [{"name": "CaseStudy_Light.json", "path": "CaseStudy_Light.json", "type": "CustomTheme"}]}],
              "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                           "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True, "useEnhancedTooltips": True,
                           "useDefaultAggregateDisplayName": True}}
    (rep / "definition" / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (rep / "definition" / "version.json").write_text(json.dumps(
        {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
         "version": "2.0.0"}, indent=2), encoding="utf-8")


def main():
    if DEF.exists():
        shutil.rmtree(DEF)
    (DEF / "tables").mkdir(parents=True)
    (DEF / "roles").mkdir()
    scaffold()
    names = []
    for t in TABLES:
        (DEF / "tables" / f"{t['name']}.tmdl").write_text(write_csv_table(t), encoding="utf-8")
        names.append(t["name"])
    for name, cols, rows, sort_by in STATIC:
        (DEF / "tables" / f"{name}.tmdl").write_text(write_static(name, cols, rows, sort_by), encoding="utf-8")
        names.append(name)
    (DEF / "tables" / "_Measures.tmdl").write_text(write_measures(), encoding="utf-8")
    names.append("_Measures")
    for rname, desc, perms in ROLES:
        (DEF / "roles" / f"{rname}.tmdl").write_text(write_role(rname, desc, perms), encoding="utf-8")

    (DEF / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n", encoding="utf-8")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tdiscourageImplicitMeasures",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "", 'annotation PBI_QueryOrder = ["DataFolder"]', "",
             'annotation PBI_ProTooling = ["TMDLView_Desktop","DevMode"]', ""]
    model += [f"ref table {q(n)}" for n in names] + [""] + [f"ref role {q(r[0])}" for r in ROLES] + [""]
    (DEF / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    (DEF / "expressions.tmdl").write_text(
        "/// Folder of the processed CSV files written by src/prepare.py and src/analysis.py (keep the final backslash).\n"
        f'expression DataFolder = "{DATA_FOLDER}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('DataFolder')}\n\n\tannotation PBI_ResultType = Text\n\n", encoding="utf-8")
    rels = []
    for i, (ft, fc, tt, tc, active) in enumerate(RELATIONSHIPS, 1):
        rels += [f"relationship rel_{i:02d}"] + ([] if active else ["\tisActive: false"]) + \
                [f"\tfromColumn: {q(ft)}.{q(fc)}", f"\ttoColumn: {q(tt)}.{q(tc)}", ""]
    (DEF / "relationships.tmdl").write_text("\n".join(rels), encoding="utf-8")
    print(f"semantic model: {len(names)} tables, {len(MEASURES)} measures, {len(RELATIONSHIPS)} relationships, {len(ROLES)} roles")


if __name__ == "__main__":
    main()
