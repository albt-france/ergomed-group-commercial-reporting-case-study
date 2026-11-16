"""Monthly commercial pack, October 2026 (8 slides, 16:9), built with python-pptx from the governed model.

Built to think-cell conventions with python-pptx (think-cell itself was not used): action titles that state the message,
stacked columns with totals, a waterfall for the variance, a Mekko for region x business, difference annotations,
one source line per slide, the same layout on every slide. Charts are native PowerPoint charts (editable) except
the Mekko, drawn with shapes (PowerPoint has no Mekko chart type).
Reusable: run it again next month (constants MONTH / YTD below); every number comes from data/processed.

Usage: python src/build_monthly_pack.py -> reports/monthly_commercial_pack.pptx
"""
import json

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from common import BUS_COLORS, FOOTER, PROC, PUB, REPORTS, pct, usdm


def susd(x, d=1):
    """Signed money: -$12.8m / +$4.1m."""
    return ("-" if x < 0 else "+") + usdm(abs(x), d)

MONTH, YTD = "October 2026", ("2026-01-01", "2026-11-01")
RGB = lambda h: RGBColor.from_string(h.lstrip("#"))  # noqa: E731
INK, INK2, MUTED, BLUE, GREY, RED, GREEN, LIGHT = "0B0B0B", "52514E", "898781", "2A78D6", "C9C7BF", "D03B3B", "1BAF7A", "F4F4F2"
FD = json.loads((PROC / "findings.json").read_text())
BUS = ["Ergomed CRO", "PrimeVigilance", "ADAMAS"]
REG = ["North America", "Europe", "Asia-Pacific", "Rest of World"]

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
N = {"n": 0}


def text(slide, x, y, w, h, s, size=12, color=INK, bold=False, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Inches(0.02)
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        runs = line if isinstance(line, list) else [(line, bold, color)]
        for t, b, c in runs:
            r = para.add_run()
            r.text, r.font.size, r.font.bold, r.font.name = t, Pt(size), b, "Segoe UI"
            r.font.color.rgb = RGB(c)
    return tb


def rect(slide, x, y, w, h, fill, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = RGB(fill)
    if line:
        s.line.color.rgb = RGB(line)
        s.line.width = Pt(0.75)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def line(slide, x1, y1, x2, y2, color=INK2, dash=False, width=1.0):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = RGB(color)
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = 4
    return c


def slide(title, tracker, source):
    """Same frame on every slide: tracker, action title, tag, source line, page number."""
    N["n"] += 1
    s = prs.slides.add_slide(BLANK)
    text(s, 0.5, 0.25, 9.5, 0.3, tracker.upper(), 10, MUTED, True)
    text(s, 0.5, 0.5, 11.2, 0.9, title, 22, INK, True)
    text(s, 10.9, 0.25, 2.0, 0.3, "SIMULATED DATA", 9, "1C5CAB", True, PP_ALIGN.RIGHT)
    line(s, 0.5, 1.42, 12.83, 1.42, "E1E0D9", width=0.75)
    text(s, 0.5, 7.0, 11.0, 0.3, "Source: " + source + " · " + FOOTER, 8, MUTED)
    text(s, 12.3, 7.0, 0.55, 0.3, str(N["n"]), 9, MUTED, align=PP_ALIGN.RIGHT)
    return s


def style_chart(chart, legend=True, gridlines=False, number_format=None, font=10):
    chart.font.size, chart.font.name = Pt(font), "Segoe UI"
    chart.font.color.rgb = RGB(INK2)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
    va = chart.value_axis
    va.has_major_gridlines = gridlines
    va.visible = False
    va.tick_labels.font.size = Pt(9)
    if number_format:
        va.tick_labels.number_format, va.tick_labels.number_format_is_linked = number_format, False
    ca = chart.category_axis
    ca.format.line.color.rgb = RGB("C9C7BF")
    ca.tick_labels.font.size = Pt(font)
    ca.has_major_gridlines = False


def fal_box(s, x, y, w, h, findings, assumptions, limits):
    rect(s, x, y, w, h, "FCFCFB", "E1E0D9")
    third = (w - 0.4) / 3
    for i, (lab, body) in enumerate((("Findings", findings), ("Assumptions", assumptions), ("Limitations", limits))):
        text(s, x + 0.15 + i * (third + 0.05), y + 0.08, third, h - 0.1, [[(lab, True, "1C5CAB")], [(body, False, INK2)]], 10)


f = pd.read_csv(PROC / "fact_opportunity.csv", parse_dates=["won_date", "decision_date"])
t = pd.read_csv(PROC / "fact_target.csv", parse_dates=["month"])
rev = pd.read_csv(PROC / "fact_revenue.csv", parse_dates=["month"])
won = f[(f.status == "Won") & (f.won_date >= YTD[0]) & (f.won_date < YTD[1])].copy()
won["m"] = won.won_date.dt.to_period("M")
K, E = FD["kpi"], FD["europe"]
d = E["decomposition"]
months = pd.period_range("2026-01", "2026-10", freq="M")

# ---------------------------------------------------------------- 1 executive summary
s = slide(f"New business is at {pct(K['attainment'])} of target year to date; closing the gap means fixing oncology conversion in CRO Europe",
          f"Monthly commercial pack · {MONTH} · Group", "governed commercial model (SIMULATED), src/analysis.py")
msgs = [
    ("Performance", f"{usdm(K['ytd_won'])} new business won Jan-Oct 2026, {pct(K['attainment'])} of the re-phased target "
                    f"({susd(K['ytd_won'] - K['ytd_target'])}); {K['growth']:+.1%} vs the same period of 2025. Book-to-bill {K['book_to_bill']:.2f}x."),
    ("Gap", f"Europe is the only large region behind ({pct(E['attainment'])}). Inside it, CRO Europe is at {pct(E['cro_eu_attainment'])}: "
            f"win rate in oncology fell from {pct(E['ta_win_rates'][0]['wr_py'])} to {pct(E['ta_win_rates'][0]['wr_ytd'])}, "
            f"while the number of decisions grew. Conversion costs {usdm(-d['conversion'])} vs last year."),
    ("Not a problem", f"The late-September peak is the usual quarter-end signing pattern ({pct(FD['quarter_end']['avg_last_week_share'])} of "
                      "each quarter's value is signed in its last week, every quarter). Flat monthly targets made mid-quarter months "
                      f"look behind ({pct(FD['phasing']['mid_quarter_att_flat'])} vs {pct(FD['phasing']['mid_quarter_att_phased'])} re-phased)."),
    ("Decisions asked", "1) Bid-defense review of the last 10 oncology losses in Europe (CRO BD lead). 2) Approve the re-phased "
                        "targets (FP&A). 3) Confirm the stage and cross-sell rules in the KPI dictionary (business leads)."),
]
for i, (h, b) in enumerate(msgs):
    y = 1.65 + i * 1.02
    rect(s, 0.5, y, 0.08, 0.82, BLUE)
    text(s, 0.75, y - 0.02, 2.3, 0.9, h, 14, INK, True)
    text(s, 3.05, y - 0.02, 9.7, 0.9, b, 13, INK2)
fal_box(s, 0.5, 5.85, 12.33, 1.05,
        "Data issues found and fixed before any figure: currency mixing, a duplicate CRM win, verbal awards counted as wins, cross-sell counted twice, a late regional file.",
        "Won = signed contract. USD at ECB monthly average of the win month. PV value = annual value x years. Targets re-phased on 2025's quarter profile (pending FP&A approval).",
        "Illustrative, simulated dataset (not Ergomed's pipeline). Causes in this pack are hypotheses until checked with the business owners.")

# ---------------------------------------------------------------- 2 stacked columns by business, with totals and target row
s = slide(f"Q3 was the strongest quarter; {usdm(K['ytd_won'])} won year to date, {pct(K['attainment'])} of the re-phased target",
          f"Monthly commercial pack · {MONTH} · New business won by month and business (USD m)", "governed model; targets: targets.xlsx re-phased")
cd = CategoryChartData()
cd.categories = [m.strftime("%b") for m in months]
for b in BUS:
    cd.add_series(b, [round(won[(won.business == b) & (won.m == m)].value_usd_governed.sum() / 1e6, 1) for m in months])
x0, y0, w0, h0 = 0.5, 1.6, 12.3, 4.3
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(x0), Inches(y0), Inches(w0), Inches(h0), cd).chart
style_chart(ch)
ch.plots[0].gap_width = 45
for ser, b in zip(ch.series, BUS):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = RGB(BUS_COLORS[b])
    if b != "ADAMAS":
        ser.data_labels.show_value = True
        ser.data_labels.font.size, ser.data_labels.font.color.rgb = Pt(8), RGB("FFFFFF")
        ser.data_labels.number_format, ser.data_labels.number_format_is_linked = "0", False
tot = [won[won.m == m].value_usd_governed.sum() for m in months]
tgt = [t[t.month.dt.to_period("M") == m].target_phased_usd.sum() for m in months]
tgf = [t[t.month.dt.to_period("M") == m].target_flat_usd.sum() for m in months]
colw = w0 / len(months)
text(s, 0.5, 6.0, 1.6, 0.3, "Total won", 10, INK, True)
text(s, 0.5, 6.28, 1.6, 0.3, "Target (re-phased)", 10, INK2)
text(s, 0.5, 6.56, 1.6, 0.3, "Attainment", 10, INK2)
for i, (a, b, c) in enumerate(zip(tot, tgt, tgf)):
    x = x0 + 0.35 + i * (w0 - 0.5) / len(months) + 0.55
    text(s, x, 6.0, 0.9, 0.3, f"{a / 1e6:.1f}", 10, INK, True, PP_ALIGN.CENTER)
    text(s, x, 6.28, 0.9, 0.3, f"{b / 1e6:.1f}", 10, INK2, align=PP_ALIGN.CENTER)
    text(s, x, 6.56, 0.9, 0.3, pct(a / b), 10, RED if a / b < 0.9 else GREEN, True, PP_ALIGN.CENTER)
PH = FD["phasing"]
text(s, 9.0, 1.5, 3.8, 0.6, f"Single months swing with a few large CRO contracts: read attainment by quarter "
     f"({', '.join(q['quarter'][-2:] + ' ' + pct(q['attainment']) for q in PH['quarters'])}). The last month of a quarter holds "
     f"{pct(PH['m3_share_avg'])} of its value on average (flat target: 33%).", 9, MUTED)

# ---------------------------------------------------------------- 3 waterfall CRO Europe
wf = pd.read_csv(PROC / "an_waterfall_cro_europe.csv")
s = slide(f"CRO Europe: {usdm(-E['cro_eu_gap'])} below target, and lower conversion is the largest single driver",
          f"Monthly commercial pack · {MONTH} · CRO Europe, Jan-Oct 2026, target to actual (USD m)",
          "governed model; decomposition: decisions x win rate x average deal, vs Jan-Oct 2025 (exact sequential substitution)")
vals = list(wf.value / 1e6)
labels = ["Target", "Growth assumed\nin target", "Volume\n(decisions)", "Conversion\n(win rate)", "Deal size", "Actual"]
base, up, down, total = [], [], [], []
run = 0
for i, v in enumerate(vals):
    if i in (0, len(vals) - 1):
        base.append(0), up.append(0), down.append(0), total.append(round(v, 1))
        run = v
    else:
        nxt = run + v
        base.append(round(min(run, nxt), 1))
        up.append(round(v, 1) if v > 0 else 0)
        down.append(round(-v, 1) if v < 0 else 0)
        total.append(0)
        run = nxt
cd = CategoryChartData()
cd.categories = labels
for name, data in (("base", base), ("Total", total), ("Increase", up), ("Decrease", down)):
    cd.add_series(name, data)
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.5), Inches(1.6), Inches(8.3), Inches(5.2), cd).chart
style_chart(ch, legend=False)
ch.plots[0].gap_width = 55
for ser, colr in zip(ch.series, (None, "52514E", GREEN, RED)):
    if colr is None:
        ser.format.fill.background()
        continue
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = RGB(colr)
    ser.data_labels.show_value = True
    ser.data_labels.number_format, ser.data_labels.number_format_is_linked = '0.0;-0.0;""', False
    ser.data_labels.position = XL_LABEL_POSITION.INSIDE_END
    ser.data_labels.font.size, ser.data_labels.font.bold = Pt(11), True
    ser.data_labels.font.color.rgb = RGB("FFFFFF")
rect(s, 9.1, 1.65, 3.73, 5.15, "FCFCFB", "E1E0D9")
ta = {r["ta"]: r for r in E["ta_win_rates"]}
text(s, 9.3, 1.75, 3.4, 5.0, [
    [("Findings", True, "1C5CAB")],
    [(f"Decisions up {d['n_cy'] - d['n_py']:+d} ({d['n_py']} -> {d['n_cy']}); win rate {pct(d['wr_py'])} -> {pct(d['wr_cy'])}.", False, INK2)],
    [(f"Oncology win rate {pct(ta['Oncology']['wr_py'])} -> {pct(ta['Oncology']['wr_ytd'])} ({ta['Oncology']['n_ytd']} decisions); "
      f"rare disease {pct(ta['Rare disease']['wr_py'])} -> {pct(ta['Rare disease']['wr_ytd'])}.", False, INK2)],
    [(f"North America oncology this year: {pct(ta['Oncology']['wr_na_ytd'])}.", False, INK2)],
    [("", False, INK2)],
    [("Hypotheses (to check)", True, "1C5CAB")],
    [("Price or competitor in European oncology bid defenses; a change in the bid team; sponsor mix. "
      "Loss reasons in the CRM are too coarse to decide.", False, INK2)],
    [("", False, INK2)],
    [("Next step", True, "1C5CAB")],
    [("Review the last 10 oncology bid-defense losses with the CRO BD lead (owner, 2 weeks).", False, INK2)],
], 11)

# ---------------------------------------------------------------- 4 Mekko region x business
s = slide("North America brings over half of new business; Europe's share is smaller than its target share",
          f"Monthly commercial pack · {MONTH} · New business won Jan-Oct 2026 by region (width) and business (height)",
          "governed model; region = client region of the opportunity")
tot_r = won.groupby("region").value_usd_governed.sum().reindex(REG).fillna(0)
grand = tot_r.sum()
X0, Y0, WW, HH = 0.7, 2.05, 9.2, 4.6
x = X0
small = []
for r in REG:
    w = WW * tot_r[r] / grand
    yb = Y0 + HH
    tr = won[won.region == r].groupby("business").value_usd_governed.sum().reindex(BUS).fillna(0)
    for b in BUS:
        h = HH * tr[b] / tot_r[r] if tot_r[r] else 0
        if h <= 0:
            continue
        rect(s, x, yb - h, w - 0.03, h, BUS_COLORS[b].lstrip("#"), "FFFFFF")
        if h > 0.32 and w > 0.55:
            text(s, x, yb - h / 2 - 0.15, w - 0.03, 0.3, pct(tr[b] / tot_r[r]), 9 if w < 1 else 11, "FFFFFF", True, PP_ALIGN.CENTER)
        yb -= h
    tgt_r = t[(t.month >= YTD[0]) & (t.month < YTD[1]) & (t.region == r)].target_phased_usd.sum()
    if w > 1.2:
        text(s, x, Y0 - 0.5, w, 0.5, [[(r, True, INK)], [(f"{usdm(tot_r[r], 0)} · {pct(tot_r[r] / grand)} of group · "
                                                         f"{pct(tot_r[r] / tgt_r)} of target", False, INK2)]], 9)
    else:
        small.append(f"{r}: {usdm(tot_r[r], 0)}, {pct(tot_r[r] / grand)} of group, {pct(tot_r[r] / tgt_r)} of target")
    x += w
text(s, X0, Y0 + HH + 0.08, WW, 0.3, "Narrow columns: " + " · ".join(small), 9, INK2)
for i, b in enumerate(BUS):
    rect(s, 10.3, 2.2 + i * 0.4, 0.25, 0.25, BUS_COLORS[b].lstrip("#"))
    text(s, 10.65, 2.17 + i * 0.4, 2.2, 0.3, b, 11, INK2)
text(s, 10.3, 3.6, 2.6, 2.8, [[("Reading the chart", True, "1C5CAB")],
                              [("Column width = region's share of group new business; segments = business mix inside the region.", False, INK2)],
                              [("", False, INK2)],
                              [(f"Europe: {pct(tot_r['Europe'] / grand)} of new business, {pct(E['attainment'])} of its target.", False, INK2)]], 10)

# ---------------------------------------------------------------- 5 conversion by therapeutic area
others = max(abs(r["wr_ytd"] - r["wr_py"]) for r in E["ta_win_rates"] if r["ta"] != "Oncology" and r["n_ytd"] >= 10)
s = slide(f"In CRO Europe, oncology conversion fell from {pct(ta['Oncology']['wr_py'])} to {pct(ta['Oncology']['wr_ytd'])}; "
          f"other areas moved by {others * 100:.0f} points or less",
          f"Monthly commercial pack · {MONTH} · CRO Europe win rate by therapeutic area, Jan-Oct 2025 vs Jan-Oct 2026",
          "governed model; win rate = won / (won + lost after proposal), by decision date")
areas = [r for r in E["ta_win_rates"] if r["n_ytd"] >= 10]
cd = CategoryChartData()
cd.categories = [f"{r['ta']} (n={r['n_ytd']})" for r in areas]
cd.add_series("Jan-Oct 2025", [round(r["wr_py"], 3) for r in areas])
cd.add_series("Jan-Oct 2026", [round(r["wr_ytd"], 3) for r in areas])
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.6), Inches(8.3), Inches(5.2), cd).chart
style_chart(ch)
ch.plots[0].gap_width, ch.plots[0].overlap = 70, -10
for ser, c in zip(ch.series, (GREY, BLUE)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = RGB(c)
    ser.data_labels.show_value = True
    ser.data_labels.number_format, ser.data_labels.number_format_is_linked = "0%", False
    ser.data_labels.font.size = Pt(11)
    ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
delta = ta["Oncology"]["wr_ytd"] - ta["Oncology"]["wr_py"]
rect(s, 1.15, 1.75, 1.5, 0.45, "FBEAEA", RED)
text(s, 1.15, 1.8, 1.5, 0.4, f"{delta * 100:+.0f} pts", 14, RED, True, PP_ALIGN.CENTER)
q = pd.read_csv(PROC / "an_oncology_quarterly.csv")
rect(s, 9.1, 1.65, 3.73, 5.15, "FCFCFB", "E1E0D9")
lines_q = [[("Oncology win rate by quarter", True, "1C5CAB")]] + [
    [(f"{r.quarter}: Europe {pct(r.onc_eu)} · N. America {pct(r.onc_na)}", False, INK2)] for r in q.itertuples()]
lines_q += [[("", False, INK2)], [("Demand did not fall", True, "1C5CAB")],
            [(f"Oncology RFPs in Europe: {E['onc_rfps_py']} (Jan-Oct 2025) vs {E['onc_rfps_cy']} (Jan-Oct 2026); "
              f"average opportunity {usdm(E['onc_avg_value_py'], 2)} vs {usdm(E['onc_avg_value_cy'], 2)}.", False, INK2)]]
text(s, 9.3, 1.75, 3.4, 5.0, lines_q, 10.5)

# ---------------------------------------------------------------- 6 book-to-bill vs public benchmarks
comp = pd.read_csv(PUB / "competitors.csv")
bench = comp[comp.year == 2025].set_index("company").book_to_bill
s = slide(f"Book-to-bill of {K['book_to_bill']:.2f}x keeps the order book growing, in line with what listed CROs reported for 2025",
          f"Monthly commercial pack · {MONTH} · Book-to-bill Jan-Oct 2026 by business, with public 2025 benchmarks",
          "governed model (SIMULATED); benchmarks PUBLIC DATA: Medpace and IQVIA 10-K FY2025, ICON FY2025 results release (27 May 2026)")
bb = [(b, FD["by_business"][b]["won"] / FD["by_business"][b]["revenue"]) for b in BUS] + [("Group", K["book_to_bill"])]
cd = CategoryChartData()
cd.categories = [b for b, _ in bb]
cd.add_series("Book-to-bill", [round(v, 2) for _, v in bb])
ch = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.7), Inches(7.6), Inches(4.6), cd).chart
style_chart(ch, legend=False)
ch.has_title = False
ch.plots[0].gap_width = 60
ser = ch.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = RGB(BLUE)
ser.data_labels.show_value = True
ser.data_labels.number_format, ser.data_labels.number_format_is_linked = '0.00"x"', False
ser.data_labels.font.size = Pt(12)
ch.category_axis.reverse_order = True
rect(s, 8.5, 1.65, 4.33, 5.15, "FCFCFB", "E1E0D9")
ob = FD["kpi"]
text(s, 8.7, 1.75, 4.0, 5.0, [
    [("Public benchmarks, FY2025 (PUBLIC DATA)", True, "1C5CAB")],
    [(f"Medpace {bench['Medpace']:.2f}x (net awards / revenue, computed from the 10-K)", False, INK2)],
    [(f"ICON {bench['ICON']:.2f}x (published; backlog method changed on 1 Oct 2025)", False, INK2)],
    [(f"IQVIA R&D Solutions {bench['IQVIA (R&D Solutions)']:.2f}x (implied: backlog change + revenue)", False, INK2)],
    [("Definitions differ: compare direction, not decimals.", False, MUTED)],
    [("", False, INK2)],
    [("Order book (SIMULATED)", True, "1C5CAB")],
    [(f"{usdm(ob['order_book_open'], 0)} at 31 Oct 2024 -> {usdm(ob['order_book'], 0)} at 31 Oct 2026 "
      "(opening + won - revenue - cancellations).", False, INK2)],
], 11)
line(s, 0.5, 6.45, 8.1, 6.45, "E1E0D9")
text(s, 0.5, 6.5, 7.6, 0.4, "Book-to-bill above 1.0x = more new business signed than revenue recognised in the period.", 9, MUTED)

# ---------------------------------------------------------------- 7 data quality: naive vs governed + actions
br = pd.read_csv(PROC / "naive_vs_governed.csv")
s = slide("Stacking the three files would mislead: five data issues are fixed before any number reaches this pack",
          f"Monthly commercial pack · {MONTH} · From 'stack the files' to the governed figure, Jan-Oct 2026 (USD m)",
          "src/prepare.py quality checks; dq_issues.csv; RECONCILIATION.md")
vals = list(br.value / 1e6)
base, up, down, total = [], [], [], []
run = 0
for i, v in enumerate(vals):
    if i in (0, len(vals) - 1):
        base.append(0), up.append(0), down.append(0), total.append(round(v, 1))
        run = v
    else:
        nxt = run + v
        base.append(round(min(run, nxt), 1)), up.append(round(v, 1) if v > 0 else 0), down.append(round(-v, 1) if v < 0 else 0), total.append(0)
        run = nxt
cd = CategoryChartData()
cd.categories = ["Naive sum", "Convert\nEUR / GBP", "Remove\nduplicate", "Won =\nsigned", "Cross-sell\nonce", "Governed"]
for name, data in (("base", base), ("Total", total), ("Increase", up), ("Decrease", down)):
    cd.add_series(name, data)
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.5), Inches(1.6), Inches(6.9), Inches(5.2), cd).chart
style_chart(ch, legend=False)
ch.plots[0].gap_width = 55
for ser, colr in zip(ch.series, (None, "52514E", GREEN, RED)):
    if colr is None:
        ser.format.fill.background()
        continue
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = RGB(colr)
    ser.data_labels.show_value = True
    ser.data_labels.number_format, ser.data_labels.number_format_is_linked = '0.0;-0.0;""', False
    ser.data_labels.position = XL_LABEL_POSITION.INSIDE_END
    ser.data_labels.font.size, ser.data_labels.font.bold = Pt(10), True
    ser.data_labels.font.color.rgb = RGB("FFFFFF")
dq = pd.read_csv(PROC / "dq_issues.csv")
acts = [("Late North America PV file (week 45)", "PV BD North America", "Escalation rule applied; file by Mon 10:00"),
        ("Re-phased targets", "FP&A", "Approve by 20 Nov"),
        ("Clients missing from the master", "Commercial Operations", f"{dq[dq.check_id == 'DQ10'].rows_flagged.sum()} clients to add"),
        ("ADAMAS tracker: merged cells, free-text status", "ADAMAS Operations", "Move to a list with drop-downs"),
        ("Verbal awards > 90 days without contract", "CRO Sales Operations", "Confirm status monthly")]
rect(s, 7.7, 1.65, 5.13, 5.15, "FCFCFB", "E1E0D9")
text(s, 7.9, 1.75, 4.8, 0.3, "Open actions (owner, next step)", 12, "1C5CAB", True)
for i, (a, o, n) in enumerate(acts):
    text(s, 7.9, 2.15 + i * 0.9, 4.8, 0.9, [[(a, True, INK)], [(o + " · " + n, False, INK2)]], 10.5)

# ---------------------------------------------------------------- 8 appendix: definitions and sources
s = slide("Appendix: the definitions behind every number in this pack", f"Monthly commercial pack · {MONTH} · Definitions",
          "docs/governance/KPI_DICTIONARY.md · docs/governance/DATA_MAPPING.md")
defs = [("New business won", "Value of contracts signed in the period, USD. CRO = contract value; PV = annual value x years; ADAMAS = confirmed quote."),
        ("Win rate", "Won / (won + lost after a proposal), by decision date. No-bids and early disqualifications excluded."),
        ("Target (re-phased)", "Annual target split by quarter, then by the 2025 month-in-quarter profile of each business."),
        ("Book-to-bill", "New business won / revenue recognised, same period."),
        ("Order book", "Opening order book + won - revenue - cancellations, monthly."),
        ("Variance decomposition", "Won = decisions x win rate x average deal; volume, conversion and deal-size effects vs last year."),
        ("Currency", "ECB monthly average of the month of the win; months not yet published use the last published month (flagged)."),
        ("Cross-sell", "An integrated CRO + PV deal: PV scope counted once, in PV.")]
for i, (k, v) in enumerate(defs):
    y = 1.65 + i * 0.64
    text(s, 0.5, y, 3.0, 0.6, k, 12, INK, True)
    text(s, 3.5, y, 9.3, 0.6, v, 12, INK2)
    line(s, 0.5, y + 0.6, 12.83, y + 0.6, "EEEDE8", width=0.5)

for k in ("author", "last_modified_by", "comments", "keywords", "subject", "category"):
    setattr(prs.core_properties, k, "")
prs.core_properties.title = f"Monthly commercial pack - {MONTH} (simulated data)"
REPORTS.mkdir(exist_ok=True)
out = REPORTS / "monthly_commercial_pack.pptx"
prs.save(out)
print("saved", out.name, N["n"], "slides")
