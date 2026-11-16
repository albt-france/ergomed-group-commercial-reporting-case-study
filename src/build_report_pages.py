"""Generate the 5 Power BI report pages (PBIR) for powerbi/ErgomedCommercial.Report.

Page grammar of the earlier case studies: title = conclusion, grey subtitle, data tag top right, footer with sources.
Numbers in titles are read from data/processed/findings.json (src/analysis.py), never typed by hand.
Usage:  python src/build_report_pages.py   (close Power BI Desktop first)
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
REPORT = ROOT / "powerbi" / "ErgomedCommercial.Report"
PAGES = REPORT / "definition" / "pages"
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
M = "_Measures"

INK, INK2, MUTED = "#0B0B0B", "#52514E", "#898781"
BLUE, GREY, LIGHT = "#2A78D6", "#B4B2A9", "#D3D1C7"
NEUTRAL, RED, RED_TINT, BLUE_TINT, GREEN_TINT = "#F0EFEC", "#D03B3B", "#F4C7C6", "#B7D3F6", "#CDEBD9"
AUTHOR = "Independent case study based on public data · not affiliated with or endorsed by Ergomed Group"
FD = json.loads((P / "findings.json").read_text())


def pct(x, d=0): return f"{100 * x:.{d}f}%"
def usdm(x, d=1): return f"${x / 1e6:,.{d}f}m"


# ---------------------------------------------------------------- expression helpers
def raw(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, int):
        s = f"{v}L"
    elif isinstance(v, float):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"Literal": {"Value": s}}

def lit(v):
    if isinstance(v, int) and not isinstance(v, bool):
        v = float(v)
    return {"expr": raw(v)}

def color(hexv):
    return {"solid": {"color": lit(hexv)}}

def col(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}

def meas(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": name}}

def agg(table, column, fn=0):          # 0 = sum, 1 = average
    return {"Aggregation": {"Expression": col(table, column), "Function": fn}}

def qref(field):
    if "Column" in field:
        c = field["Column"]
        return f'{c["Expression"]["SourceRef"]["Entity"]}.{c["Property"]}'
    if "Measure" in field:
        return f'{M}.{field["Measure"]["Property"]}'
    c = field["Aggregation"]["Expression"]["Column"]
    fn = "Sum" if field["Aggregation"]["Function"] == 0 else "Avg"
    return f'{fn}({c["Expression"]["SourceRef"]["Entity"]}.{c["Property"]})'

def proj(field, label=None):
    p = {"field": field, "queryRef": qref(field)}
    if "Column" in field:
        p["nativeQueryRef"] = field["Column"]["Property"]
    elif "Measure" in field:
        p["nativeQueryRef"] = field["Measure"]["Property"]
    else:
        p["nativeQueryRef"] = field["Aggregation"]["Expression"]["Column"]["Property"]
        p["displayName"] = field["Aggregation"]["Expression"]["Column"]["Property"]
    if label:
        p["displayName"] = label
    return p

def C(t, c): return col(t, c)
def Ms(*names): return [meas(n) for n in names]

def series_color(field, hexv):
    return {"properties": {"fill": color(hexv)}, "selector": {"metadata": qref(field)}}

def value_color(table, column, value, hexv):
    """Colour of one category / series value (e.g. the 'Markov' series)."""
    return {"properties": {"fill": color(hexv)},
            "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col(table, column),
                                                               "Right": raw(value)}}}]}}

def ref_line(value, label, hexv=INK2, selector_id="1"):
    v = {"expr": value} if isinstance(value, dict) else lit(value)
    return {"properties": {"show": lit(True), "value": v, "displayName": lit(label), "lineColor": color(hexv),
                           "style": lit("dashed"), "dataLabelShow": lit(True), "dataLabelColor": color(hexv)},
            "selector": {"id": selector_id}}

def bg_rule(field, lo, hi, mid=None, mid_value=None):
    """Background-colour scale (conditional formatting) on a table/matrix value column."""
    rule = {"min": {"color": raw(lo)}, "max": {"color": raw(hi)},
            "nullColoringStrategy": {"strategy": raw("asZero")}}
    key = "linearGradient2"
    if mid:
        key = "linearGradient3"
        rule["mid"] = {"color": raw(mid)}
        if mid_value is not None:
            rule["mid"]["value"] = raw(float(mid_value))
    return {"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": field, "FillRule": {key: rule}}}}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": qref(field)}}

def table_style(extra_values=(), matrix=False, font=12):
    """Readable table: 12pt text, no misleading total row/column."""
    fs = {"properties": {"fontSize": lit(font)}}
    objs = {"values": [fs, *extra_values], "columnHeaders": [{"properties": {"fontSize": lit(font), "fontColor": color(INK2)}}]}
    if matrix:
        objs["rowHeaders"] = [fs]
        objs["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
    else:
        objs["total"] = [{"properties": {"totals": lit(False)}}]
    return objs

def no_legend(extra=None):
    o = {"legend": [{"properties": {"show": lit(False)}}]}
    o.update(extra or {})
    return o

def data_labels(fmt_color=INK):
    return [{"properties": {"show": lit(True), "color": color(fmt_color)}}]

def flt(table, column, values, negate=False):
    """Visual-level filter: keep (or exclude) a list of values."""
    return (table, column, values, negate)

def slicer_selection(table, column, value):
    return {"filter": {"filter": {"Version": 2, "From": [{"Name": "s", "Entity": table, "Type": 0}],
                                  "Where": [{"Condition": {"In": {
                                      "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": column}}],
                                      "Values": [[raw(value)]]}}}]}}}


# ---------------------------------------------------------------- page / visual builders
class Page:
    def __init__(self, pid, name):
        self.pid, self.name, self.visuals, self.interactions, self.n = pid, name, [], [], 0

    def _add(self, vid, x, y, w, h, visual):
        self.n += 1
        self.visuals.append({"$schema": VC_SCHEMA, "name": vid,
                             "position": {"x": round(x), "y": round(y), "z": self.n * 1000,
                                          "height": round(h), "width": round(w), "tabOrder": self.n * 1000},
                             "visual": visual})
        return vid

    def chart(self, vid, vtype, x, y, w, h, roles, title=None, objects=None, labels=None, sort=None, filters=()):
        labels = labels or {}
        visual = {"visualType": vtype,
                  "query": {"queryState": {r: {"projections": [proj(f, labels.get(qref(f))) for f in fs]}
                                           for r, fs in roles.items() if fs}},
                  "drillFilterOtherVisuals": True}
        if sort:
            field, direction = sort
            visual["query"]["sortDefinition"] = {"sort": [{"field": field, "direction": direction}],
                                                 "isDefaultSort": False}
        if objects:
            visual["objects"] = objects
        vco = {"subTitle": [{"properties": {"show": lit(False)}}]}
        vco["title"] = [{"properties": {"show": lit(bool(title)), **({"text": lit(title)} if title else {})}}]
        visual["visualContainerObjects"] = vco
        vid = self._add(vid, x, y, w, h, visual)
        fl = []
        for i, (table, column, values, negate) in enumerate(filters):
            cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                           "Values": [[raw(v)] for v in values]}}
            if negate:
                cond = {"Not": {"Expression": cond}}
            fl.append({"name": f"visualFilter{i}", "type": "Categorical", "field": col(table, column),
                       "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
                                  "Where": [{"Condition": cond}]}})
        if fl:
            self.visuals[-1]["filterConfig"] = {"filters": fl}
        return vid

    def text(self, vid, x, y, w, h, paragraphs, boxed=False):
        """paragraphs: list of paragraphs; each paragraph = list of (text, size, colour, bold) runs."""
        paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "color": c,
                                                         **({"fontWeight": "bold"} if b else {})}}
                               for t, s, c, b in runs]} for runs in paragraphs]
        visual = {"visualType": "textbox",
                  "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                  "visualContainerObjects": {"background": [{"properties": {"show": lit(boxed)}}],
                                             "border": [{"properties": {"show": lit(boxed)}}],
                                             **({"padding": [{"properties": {"top": lit(16), "bottom": lit(16),
                                                                             "left": lit(20), "right": lit(20)}}]}
                                                if boxed else {})}}
        return self._add(vid, x, y, w, h, visual)

    def header(self, title, conclusion, tag):
        self.text("title", 32, 20, 1500, 56, [[(title, 24, INK, True)]])
        self.text("tag", 1540, 28, 348, 40, [[(tag, 10, INK2, True)]])
        self.text("conclusion", 32, 76, 1856, 64, [[(conclusion, 13, INK2, False)]])

    def footer(self, source):
        self.text("footer", 32, 1040, 1856, 32, [[(source + "   ·   " + AUTHOR, 9, MUTED, False)]])

    def slicer(self, vid, x, y, w, h, field, title, dropdown=True, single=False, selected=None):
        objs = {"header": [{"properties": {"show": lit(False)}}]}
        if dropdown:
            objs["data"] = [{"properties": {"mode": lit("Dropdown")}}]
        if single:
            objs["selection"] = [{"properties": {"singleSelect": lit(True), "strictSingleSelect": lit(True)}}]
        if selected:
            objs["general"] = [{"properties": slicer_selection(*selected)}]
        return self.chart(vid, "slicer", x, y, w, h, {"Values": [field]}, title, objs)

    def card(self, vid, x, y, w, h, measure, title, filters=()):
        return self.chart(vid, "card", x, y, w, h, {"Values": [meas(measure)]}, title,
                          {"labels": [{"properties": {"color": color(INK), "fontSize": lit(28)}}],
                           "categoryLabels": [{"properties": {"show": lit(False)}}]}, filters=filters)

    def write(self):
        d = PAGES / self.pid
        if d.exists():
            shutil.rmtree(d)
        (d / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.pid, "displayName": self.name,
                "displayOption": "FitToPage", "height": 1080, "width": 1920}
        if self.interactions:
            page["visualInteractions"] = self.interactions
        (d / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        for v in self.visuals:
            vd = d / "visuals" / v["name"]
            vd.mkdir()
            (vd / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")



# ---------------------------------------------------------------- layout grid
L, R, TOP, BOT, GAP = 32, 1888, 156, 1028, 24
W = R - L


def cols(n, x0=L, x1=R):
    w = (x1 - x0 - (n - 1) * GAP) / n
    return [(x0 + i * (w + GAP), w) for i in range(n)]


def kpi_row(p, items, y=TOP, h=120, x0=L, x1=R):
    for (x, w), (m, t) in zip(cols(len(items), x0, x1), items):
        p.card("kpi_" + "".join(ch for ch in m if ch.isalnum())[:30], x, y, w, h, m, t)
    return y + h + GAP


def kpis(p, items, y=TOP, h=118, filters=()):
    for (x, w), (m, t) in zip(cols(len(items)), items):
        p.card("kpi_" + "".join(ch for ch in m if ch.isalnum())[:30], x, y, w, h, m, t, filters=filters)
    return y + h + GAP


CLOSED = [flt("DimDate", "is_closed_month", [True])]
Y2026 = [flt("DimDate", "year", [2026])]
K, E, PH, QE, DI = FD["kpi"], FD["europe"], FD["phasing"], FD["quarter_end"], FD["data_issues"]
pages = []

# ======================= 1 Group overview =======================
p = Page("e1000000000000000001", "Group overview")
p.header(f"New business won is at {pct(K['attainment'])} of target year to date; Europe ({pct(E['attainment'])}) is the only large region behind",
         f"Jan-Oct 2026, three businesses in USD at ECB monthly rates: {usdm(K['ytd_won'])} won vs {usdm(K['ytd_target'])} re-phased target. "
         f"Book-to-bill {K['book_to_bill']:.2f}x, win rate {pct(K['win_rate'])} (last year {pct(K['win_rate_py'])}). "
         "RLS limits what each user sees (business x region).",
         "SIMULATED · ILLUSTRATIVE DATASET")
y = kpis(p, [("New Business Won", "New business won (USD)"), ("Attainment %", "Attainment vs re-phased target"),
             ("Book-to-Bill", "Book-to-bill"), ("Win Rate", "Win rate (count)"), ("Weighted Pipeline", "Weighted open pipeline")],
         filters=CLOSED + Y2026)
(xa, wa), (xb, wb) = cols(2)
h1 = (BOT - y - GAP) / 2
p.chart("col_business", "clusteredColumnChart", xa, y, wa, h1,
        {"Category": [C("DimBusiness", "business")], "Y": Ms("New Business Won", "Target")},
        "New business won vs target, by business (Jan-Oct 2026)",
        {"dataPoint": [series_color(meas("New Business Won"), BLUE), series_color(meas("Target"), GREY)], "labels": data_labels()},
        filters=CLOSED + Y2026)
p.chart("mx_attain", "pivotTable", xb, y, wb, h1,
        {"Rows": [C("DimRegion", "region")], "Columns": [C("DimBusiness", "business")], "Values": Ms("Attainment %")},
        "Attainment by region and business (red below 100%)",
        table_style([bg_rule(meas("Attainment %"), RED_TINT, GREEN_TINT, "#FFFFFF", 1.0)], matrix=True, font=13),
        filters=CLOSED + Y2026)
p.chart("line_month", "lineClusteredColumnComboChart", xa, y + h1 + GAP, W, h1,
        {"Category": [C("DimDate", "month_label")], "Y": Ms("New Business Won"), "Y2": Ms("Target", "Target (as received)")},
        "Monthly new business won vs target: re-phased (quarter-end profile) and as received (annual / 12)",
        {"dataPoint": [series_color(meas("New Business Won"), BLUE)]}, filters=CLOSED + Y2026)
p.footer("SIMULATED commercial dataset (seed 42) · FX: ECB monthly averages · model: powerbi/ErgomedCommercial.SemanticModel")
pages.append(p)

# ======================= 2 Pipeline & conversion =======================
p = Page("e2000000000000000002", "Pipeline & conversion")
p.header("One funnel for three businesses: a CRO verbal award is not a win until the contract is signed",
         "Each source stage is mapped to five common stages (table). Win rate = won / (won + lost after a proposal), by decision "
         "date; disqualified and no-bid opportunities are excluded. Open pipeline is shown at the data cut (8 Nov 2026).",
         "SIMULATED · ILLUSTRATIVE DATASET")
p.slicer("sl_business", L, TOP, 420, 64, C("DimBusiness", "business"), "Business")
p.slicer("sl_year", L + 444, TOP, 260, 64, C("DimDate", "year"), "Decision year", selected=("DimDate", "year", 2026))
y = TOP + 64 + GAP
(xa, wa), (xb, wb), (xc, wc) = cols(3)
h1 = (BOT - y - GAP) / 2
p.chart("funnel_open", "funnel", xa, y, wa, h1, {"Category": [C("DimStage", "common_stage")], "Y": Ms("Open Pipeline")},
        "Open pipeline by common stage (USD)", {"labels": data_labels()}, filters=[flt("FactOpportunity", "status", ["Open"])])
p.chart("bar_ta", "clusteredBarChart", xb, y, wb, h1, {"Category": [C("DimTherapeuticArea", "therapeutic_area")], "Y": Ms("Win Rate", "Win Rate PY")},
        "Win rate by therapeutic area: this year vs last year",
        {"dataPoint": [series_color(meas("Win Rate"), BLUE), series_color(meas("Win Rate PY"), GREY)], "labels": data_labels()})
p.chart("bar_cycle", "clusteredBarChart", xc, y, wc, h1, {"Category": [C("DimBusiness", "business")], "Y": Ms("Sales Cycle (days)")},
        "Sales cycle, creation to signature (days)", {"dataPoint": [series_color(meas("Sales Cycle (days)"), BLUE)], "labels": data_labels()})
p.chart("tbl_map", "tableEx", xa, y + h1 + GAP, wa + wb + GAP, h1,
        {"Values": [C("StageMap", "business"), C("StageMap", "source_stage"), C("StageMap", "common_stage"), C("StageMap", "status"),
                    C("StageMap", "note")]}, "Stage mapping (docs/governance/mappings/stage_map.csv)", table_style(font=11))
p.chart("mx_conv", "pivotTable", xc, y + h1 + GAP, wc, h1,
        {"Rows": [C("DimBusiness", "business")], "Values": Ms("Decisions", "Win Rate", "Win Rate (value)", "Verbal Awards Pending")},
        "Conversion by business", table_style(matrix=True, font=12))
p.footer("SIMULATED · stage mapping: docs/governance/mappings/stage_map.csv · KPI definitions: docs/governance/KPI_DICTIONARY.md")
pages.append(p)

# ======================= 3 Targets & variance =======================
d = E["decomposition"]
p = Page("e3000000000000000003", "Targets & variance")
p.header(f"CRO Europe is at {pct(E['cro_eu_attainment'])} of target: lower conversion costs {usdm(-d['conversion'])} vs last year, "
         f"while volume adds {usdm(d['volume'])}",
         "Won value = decisions x win rate x average deal. Waterfall: last year's won value, then volume, conversion and deal-size "
         "effects (exact decomposition). Flat targets (annual / 12) make mid-quarter months look behind "
         f"({pct(PH['mid_quarter_att_flat'])} vs {pct(PH['mid_quarter_att_phased'])} re-phased).",
         "SIMULATED · ILLUSTRATIVE DATASET")
p.slicer("sl_b3", L, TOP, 420, 64, C("DimBusiness", "business"), "Business", single=True, selected=("DimBusiness", "business", "Ergomed CRO"))
p.slicer("sl_r3", L + 444, TOP, 420, 64, C("DimRegion", "region"), "Region", single=True, selected=("DimRegion", "region", "Europe"))
y = TOP + 64 + GAP
(xa, wa), (xb, wb) = cols(2)
h1 = (BOT - y - GAP) / 2
p.chart("wf_var", "waterfallChart", xa, y, wa, BOT - y, {"Category": [C("VarianceStep", "step")], "Y": Ms("Variance Bridge")},
        "From last year's won value to this year's (Jan-Oct, by decision date)", {"labels": data_labels()}, filters=CLOSED + Y2026,
        sort=(C("VarianceStep", "step_sort"), "Ascending"))
p.chart("mx_target", "pivotTable", xb, y, wb, h1,
        {"Rows": [C("DimDate", "month_label")], "Values": Ms("New Business Won", "Target (as received)", "Attainment % (as received)",
                                                            "Target", "Attainment %")},
        "Attainment by month: target as received vs re-phased",
        table_style([bg_rule(meas("Attainment % (as received)"), RED_TINT, GREEN_TINT, "#FFFFFF", 1.0),
                     bg_rule(meas("Attainment %"), RED_TINT, GREEN_TINT, "#FFFFFF", 1.0)], matrix=True, font=12), filters=CLOSED + Y2026)
p.chart("tbl_effects", "pivotTable", xb, y + h1 + GAP, wb, h1,
        {"Rows": [C("DimTherapeuticArea", "therapeutic_area")], "Values": Ms("Decisions", "Win Rate", "Win Rate PY", "Conversion Effect")},
        "Where the conversion effect comes from (therapeutic area)", table_style(matrix=True, font=12), filters=CLOSED + Y2026)
p.footer("SIMULATED · decomposition: measures Volume / Conversion / Deal Size Effect · targets: data/simulated/targets.xlsx re-phased in src/prepare.py")
pages.append(p)

# ======================= 4 Business drill-down =======================
p = Page("e4000000000000000004", "Business drill-down")
p.header("Each business keeps its own way of selling: pick one to see its source stages, value basis and specific KPIs",
         "CRO: contract value in EUR, RFP and bid-defense stages, verbal awards. PrimeVigilance: recurring contracts, value = annual value "
         "x years (USD). ADAMAS: small audit quotes in GBP from a manual tracker. All are converted and mapped in the group view.",
         "SIMULATED · ILLUSTRATIVE DATASET")
p.slicer("sl_b4", L, TOP, 520, 64, C("DimBusiness", "business"), "Business", single=True, selected=("DimBusiness", "business", "Ergomed CRO"))
p.chart("tbl_basis", "tableEx", L + 544, TOP, R - L - 544, 64,
        {"Values": [C("DimBusiness", "source_currency"), C("DimBusiness", "value_basis"), C("DimBusiness", "won_definition")]},
        None, table_style(font=11))
y = kpis(p, [("New Business Won", "New business won"), ("Book-to-Bill", "Book-to-bill"), ("Win Rate", "Win rate"),
             ("Average Deal Size", "Average deal size"), ("Order Book", "Order book (closing)")], y=TOP + 64 + GAP, filters=CLOSED + Y2026)
(xa, wa), (xb, wb) = cols(2)
p.chart("bar_stage", "clusteredBarChart", xa, y, wa, BOT - y, {"Category": [C("FactOpportunity", "source_stage")], "Y": Ms("Open Pipeline")},
        "Open pipeline by SOURCE stage (the business's own names)", {"dataPoint": [series_color(meas("Open Pipeline"), BLUE)], "labels": data_labels()},
        filters=[flt("FactOpportunity", "status", ["Open"])])
p.chart("mx_detail", "pivotTable", xb, y, wb, BOT - y,
        {"Rows": [C("FactOpportunity", "detail")], "Values": Ms("New Business Won", "Deals Won", "Win Rate", "Sales Cycle (days)")},
        "By phase (CRO), service (PV) or audit type (ADAMAS), Jan-Oct 2026", table_style(matrix=True, font=12), filters=CLOSED + Y2026)
p.footer("SIMULATED · sources: cro_crm.xlsx (EUR), pv_pipeline.csv (USD), adamas_tracker.xlsx (GBP)")
pages.append(p)

# ======================= 5 Data health =======================
late = DI["late_source"][0] if DI["late_source"] else None
p = Page("e5000000000000000005", "Data health")
p.header((f"One source was late this week ({late['data_owner']}); {DI['dq_open']} quality checks are open with a named owner"
          if late else f"All sources on time; {DI['dq_open']} quality checks open"),
         "Freshness and completeness of each weekly submission, automatic quality checks by source and data owner, and the "
         "reconciliation of every source total with the model. The naive 'stack the files' total is shown next to the governed one.",
         "SIMULATED · DATA GOVERNANCE")
y = kpis(p, [("Late Sources", "Late submissions (week 45)"), ("Open DQ Issues", "Open quality checks"),
             ("On-Time Rate (52 weeks)", "On-time submissions, 52 weeks")])
(xa, wa), (xb, wb) = cols(2)
p.chart("tbl_health", "tableEx", xa, y, W, 210,
        {"Values": [C("DataHealth", "data_owner"), C("DataHealth", "source_file"), C("DataHealth", "deadline"), C("DataHealth", "received"),
                    C("DataHealth", "status"), C("DataHealth", "completeness"), C("DataHealth", "rows_in_model"), C("DataHealth", "impact")]},
        "Weekly submissions, week ending 8 Nov 2026", table_style(font=11))
y2 = y + 210 + GAP
p.chart("tbl_dq", "tableEx", xa, y2, wa, BOT - y2,
        {"Values": [C("DQIssues", "check_id"), C("DQIssues", "check"), C("DQIssues", "data_owner"), C("DQIssues", "rows_flagged"),
                    C("DQIssues", "severity"), C("DQIssues", "status")]}, "Quality checks (src/prepare.py)", table_style(font=10))
hb = (BOT - y2 - GAP) / 2
p.chart("tbl_rec", "tableEx", xb, y2, wb, hb,
        {"Values": [C("Reconciliation", "source"), C("Reconciliation", "check"), agg("Reconciliation", "source_value"),
                    agg("Reconciliation", "model_value"), C("Reconciliation", "note")]}, "Reconciliation: source vs model", table_style(font=10))
p.chart("tbl_naive", "tableEx", xb, y2 + hb + GAP, wb, hb,
        {"Values": [C("NaiveBridge", "step"), agg("NaiveBridge", "value"), C("NaiveBridge", "note")]},
        "Naive vs governed new business, Jan-Oct 2026", table_style(font=10))
p.footer("SIMULATED · source log: data/simulated/source_log.csv · deadlines: docs/governance/REPORTING_CALENDAR.md")
pages.append(p)

# ---------------------------------------------------------------- write
PAGES.mkdir(parents=True, exist_ok=True)
keep = {pg.pid for pg in pages}
for d_ in PAGES.iterdir():
    if d_.is_dir() and d_.name not in keep:
        shutil.rmtree(d_)
for pg in pages:
    pg.write()
meta = {"$schema": PAGES_SCHEMA, "pageOrder": [pg.pid for pg in pages], "activePageName": pages[0].pid}
(PAGES / "pages.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("pages:", [(pg.name, len(pg.visuals)) for pg in pages])
