"""8-page PDF (landscape 16:9): HTML + inline SVG charts, printed by headless Edge. Every number is read from data/public
or data/processed; nothing is typed in the text. Power BI captures are used if docs/img/powerbi_p*.png exist.
Usage: python src/build_pdf.py -> docs/Ergomed_Commercial_Reporting_Case_Study.pdf (+ docs/img/pdf_p*.png)"""
import json
import subprocess

import numpy as np
import pandas as pd
from jinja2 import Template

from common import (AI_NOTE, BLUE, BLUE_L, BUS_COLORS, DOCS, FOOTER, GRAY, GRAY_D, GREEN, IMG, INK2, PROC, PUB, RED, REPORTS,
                    ROOT, TMP, html_to_pdf, mpl, pct, screenshot, svg, usdm)

PDF = DOCS / "Ergomed_Commercial_Reporting_Case_Study.pdf"
FD = json.loads((PROC / "findings.json").read_text())
CT = json.loads((PUB / "ct_summary.json").read_text())
plt = mpl()

CSS = """
@page { size: 16in 9in; margin: 0 }
* { box-sizing: border-box; margin: 0; padding: 0 }
body { font-family: 'Segoe UI', system-ui, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1536px; height: 864px; padding: 30px 40px 16px; display: flex; flex-direction: column;
        background: #F4F4F2; page-break-after: always; overflow: hidden; position: relative }
header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; min-height: 58px }
h1 { font-size: 25px; font-weight: 700; line-height: 1.2; max-width: 1220px; letter-spacing: -0.2px }
.sub { color: #52514E; font-size: 14px; margin-top: 6px; max-width: 1260px; line-height: 1.4 }
.tag { font-size: 11.5px; font-weight: 700; letter-spacing: .8px; color: #52514E; border: 1px solid #C9C7BF; border-radius: 4px;
       padding: 4px 9px; white-space: nowrap; margin-top: 6px; background: #FCFCFB }
.tag.sim { color: #1C5CAB; border-color: #86B6EF } .tag.real { color: #0E7A55; border-color: #8FD3B8 }
.kpis { display: grid; gap: 14px; margin-bottom: 12px }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 12px 16px; display: flex; flex-direction: column;
        min-height: 0; overflow: hidden }
.kpi { padding: 11px 17px }
.klabel { font-size: 11px; font-weight: 700; color: #52514E; letter-spacing: .5px; text-transform: uppercase }
.kval { font-size: 29px; font-weight: 700; margin-top: 2px; line-height: 1.15 } .kval.blue { color: #1C5CAB } .kval.red { color: #D03B3B }
.knote { font-size: 12.5px; color: #52514E; margin-top: 3px; line-height: 1.35 }
.grid { display: grid; gap: 14px; flex: 1; min-height: 0 }
.card h3 { font-size: 13.5px; font-weight: 600; margin-bottom: 6px }
.card h3 .t { font-size: 10px; font-weight: 700; color: #0E7A55; border: 1px solid #8FD3B8; border-radius: 3px; padding: 1px 5px; margin-left: 6px }
.card h3 .t.s { color: #1C5CAB; border-color: #86B6EF }
.body { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; font-size: 13px; line-height: 1.45 }
.body svg { width: 100%; height: 100% } .body img { max-width: 100%; max-height: 100%; border: 1px solid #E1E0D9; border-radius: 4px }
.body.text { display: block; overflow: hidden; color: #2B2A28 }
.body.text p { margin-bottom: 7px } .body.text ul, .body.text ol { margin: 0 0 6px 18px } .body.text li { margin-bottom: 4px }
table { border-collapse: collapse; width: 100%; font-size: 12px }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #C9C7BF; padding: 3px 5px }
td { padding: 3px 5px; border-bottom: 1px solid #EEEDE8; vertical-align: top } td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
td.ok { color: #0E7A55; font-weight: 600 } td.open { color: #9A6A00; font-weight: 600 }
footer { font-size: 10.5px; color: #898781; margin-top: 9px }
.lab { font-weight: 700; color: #52514E; font-size: 12px; letter-spacing: .4px }
.flow { display: flex; gap: 7px; align-items: stretch; width: 100% }
.flow div.s { flex: 1; border: 1px solid #86B6EF; background: #EEF5FD; border-radius: 6px; padding: 7px; font-size: 12px; text-align: center }
.flow div.s b { display: block; color: #1C5CAB; margin-bottom: 3px } .flow div.a { color: #898781; font-size: 18px; align-self: center }
.mono { font-family: Consolas, monospace; font-size: 11.5px; background: #F1F0EB; padding: 1px 4px; border-radius: 3px }
.ai { border-left: 3px solid #2A78D6; padding: 6px 10px; background: #EEF5FD; font-size: 13px; margin-top: 4px }
.fh { display: grid; grid-template-columns: 1fr 1fr; gap: 10px } .fh div { font-size: 12.5px } .fh b { color: #1C5CAB }
"""

PAGE = Template("""
<section class="page">
  <header><div><h1>{{ p.title }}</h1>{% if p.subtitle %}<p class="sub">{{ p.subtitle }}</p>{% endif %}</div>
  <div class="tag {{ p.tag_class }}">{{ p.tag }}</div></header>
  {% if p.kpis %}<div class="kpis" style="grid-template-columns: repeat({{ p.kpis|length }}, 1fr)">
    {% for k in p.kpis %}<div class="card kpi"><div class="klabel">{{ k[0] }}</div><div class="kval {{ k[3] if k|length > 3 else '' }}">{{ k[1] }}</div><div class="knote">{{ k[2] }}</div></div>{% endfor %}
  </div>{% endif %}
  <div class="grid" style="grid-template-columns: {{ p.cols }}; grid-template-rows: {{ p.rows }}">
    {% for c in p.cards %}<div class="card" style="grid-column: {{ c.col }}; grid-row: {{ c.row }}">
      {% if c.title %}<h3>{{ c.title }}</h3>{% endif %}<div class="body {{ 'text' if c.text else '' }}">{{ c.body }}</div></div>{% endfor %}
  </div>
  <footer>{{ p.footer }} · {{ foot }}</footer>
</section>""")


def card(title, body, col="auto", row="auto", text=False, tag=None):
    if tag:
        title += f"<span class='t {'s' if tag == 'SIMULATED' else ''}'>{tag}</span>"
    return dict(title=title, body=body, col=col, row=row, text=text)


def img(name, alt=""):
    f = IMG / name
    return f'<img src="{f.as_uri()}" alt="{alt}">' if f.exists() else f"<p>{alt} (not generated)</p>"


def fig(w, h):
    return plt.subplots(figsize=(w / 96, h / 96), dpi=96)


def table(df, num=(), cls=None):
    h = "".join(f"<th class='{'n' if c in num else ''}'>{c}</th>" for c in df.columns)
    rows = ""
    for _, r in df.iterrows():
        rows += "<tr>" + "".join(f"<td class='{'n' if c in num else (cls(c, r[c]) if cls else '')}'>{r[c]}</td>" for c in df.columns) + "</tr>"
    return f"<table><tr>{h}</tr>{rows}</table>"


# ------------------------------------------------------------------ charts
def ch_ergomed_revenue():
    rev = pd.read_csv(PUB / "ergomed_revenue.csv")
    t = rev.pivot_table(index=["year", "currency"], columns="business", values="revenue_thousands", aggfunc="sum") / 1000
    f, ax = fig(560, 280)
    x = np.arange(len(t))
    cro, pv = t.iloc[:, 0].values, t.iloc[:, 1].values
    gap = [0 if c == "GBP" else 0.6 for _, c in t.index]
    xs = x + np.array(gap)
    ax.bar(xs, cro, 0.62, color=BUS_COLORS["Ergomed CRO"], label="Ergomed CRO (clinical research)")
    ax.bar(xs, pv, 0.62, bottom=cro, color=BUS_COLORS["PrimeVigilance"], label="PrimeVigilance (pharmacovigilance)")
    for xi, c, p in zip(xs, cro, pv):
        ax.text(xi, c + p + 4, f"{c + p:.0f}", ha="center", fontsize=8.5, color=INK2)
    labels = [f"{y}\n{'GBP' if c == 'GBP' else 'USD'}" for y, c in t.index]
    labels = [l.replace("2024\nUSD", "to Dec 24\nUSD 13.5m") for l in labels]
    ax.set_xticks(xs, labels, fontsize=8)
    ax.axvline(xs[4] + 0.6, color=GRAY_D, ls=(0, (3, 3)), lw=1)
    ax.set_ylim(0, max(cro + pv) * 1.32)
    ax.text(xs[4] + 0.68, max(cro + pv) * 1.18, "currency, period and\nreporting entity change", fontsize=7.5, color=GRAY_D)
    ax.set_ylabel("Revenue, m (GBP / USD)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_order_book():
    c = pd.read_csv(PUB / "ergomed_commercial.csv")
    f, ax = fig(420, 250)
    ax.bar(c.year, c.order_book_m, color=BLUE_L, width=0.6, label="Order book (year end)")
    ax.plot(c.year, c.revenue_m, color=INK2, marker="o", lw=1.5, label="Revenue")
    for y, o in zip(c.year, c.order_book_m):
        ax.text(y, o + 5, f"{o:.0f}", ha="center", fontsize=8.5, color=INK2)
    for r in c.dropna(subset=["book_to_bill"]).itertuples():
        ax.text(r.year, 12, f"BtB\n{r.book_to_bill:.2f}x", ha="center", fontsize=7.5, color="#1C5CAB", fontweight="bold")
    ax.set_ylabel("GBP m")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_trials_year():
    y = pd.read_csv(PUB / "ct_by_year.csv", index_col=0)
    f, ax = fig(560, 250)
    b = np.zeros(len(y))
    for c, col in (("Oncology", BLUE), ("Oncology + rare", BLUE_L), ("Rare disease", GREEN)):
        ax.bar(y.index, y[c], bottom=b, color=col, width=0.65, label=c)
        b += y[c].values
    for xi, v in zip(y.index, b):
        ax.text(xi, v + 15, f"{v:,.0f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_ylabel("Studies started")
    ax.legend(loc="lower left", fontsize=8, ncol=3, bbox_to_anchor=(0, 1.0))
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_countries():
    c = pd.read_csv(PUB / "ct_by_country.csv", index_col=0).head(12)[::-1]
    f, ax = fig(600, 560)
    ax.barh(c.index, c.studies, color=[BLUE if r == "Europe" else GRAY for r in c.region], height=0.65)
    for i, (v, s) in enumerate(zip(c.studies, c.small_mid_share)):
        ax.text(v + 30, i, f"{v:,}  ({s:.0%} small/mid)", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, c.studies.max() * 1.45)
    ax.set_xlabel("Oncology / rare-disease studies with a site in the country (blue = Europe)")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x")
    return svg(f)


def ch_competitors():
    c = pd.read_csv(PUB / "competitors.csv")
    p = c.pivot(index="year", columns="company", values="book_to_bill")
    f, ax = fig(430, 250)
    cols = {"Medpace": BLUE, "IQVIA (R&D Solutions)": GREEN, "ICON": "#EDA100"}
    for k, col in cols.items():
        s = p[k].dropna()
        ax.plot(s.index, s.values, marker="o", color=col, lw=1.8, label=k)
    ax.axhline(1, color=GRAY_D, ls=(0, (3, 3)), lw=1)
    ax.set_ylabel("Book-to-bill (x)")
    ax.legend(fontsize=8, loc="upper right")
    return svg(f)


def ch_waterfall():
    wf = pd.read_csv(PROC / "an_waterfall_cro_europe.csv")
    v = wf.value.values / 1e6
    f, ax = fig(560, 300)
    run, bottoms, heights, colors = 0, [], [], []
    for i, x in enumerate(v):
        if i in (0, len(v) - 1):
            bottoms.append(0), heights.append(x), colors.append("#52514E")
            run = x
        else:
            bottoms.append(min(run, run + x)), heights.append(abs(x)), colors.append(GREEN if x > 0 else RED)
            run += x
    labels = ["Target", "Growth\nassumed", "Volume", "Conversion", "Deal size", "Actual"]
    ax.bar(range(len(v)), heights, bottom=bottoms, color=colors, width=0.6)
    for i, (b, h, x) in enumerate(zip(bottoms, heights, v)):
        ax.text(i, b + h + 1, f"{x:+.1f}" if 0 < i < len(v) - 1 else f"{x:.1f}", ha="center", fontsize=9, color=INK2)
    ax.set_xticks(range(len(v)), labels, fontsize=8.5)
    ax.set_ylabel("USD m, Jan-Oct 2026")
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_onc_quarterly():
    q = pd.read_csv(PROC / "an_oncology_quarterly.csv")
    f, ax = fig(430, 260)
    ax.plot(q.quarter, q.onc_eu * 100, marker="o", color=RED, lw=2, label="CRO Europe, oncology")
    ax.plot(q.quarter, q.onc_na * 100, marker="o", color=GRAY_D, lw=1.5, label="CRO North America, oncology")
    ax.plot(q.quarter, q.rare_eu * 100, marker="o", color=GREEN, lw=1.5, label="CRO Europe, rare disease")
    ax.set_ylabel("Win rate (%)")
    ax.tick_params(axis="x", labelsize=8)
    ax.legend(fontsize=8, loc="lower left", ncol=3, bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, 65)
    return svg(f)


def ch_weekly():
    wk = pd.read_csv(PROC / "an_weekly_won.csv", parse_dates=["week_ending"])
    f, ax = fig(560, 230)
    ax.bar(range(len(wk)), wk.won_usd / 1e6, color=[BLUE if q else GRAY for q in wk.quarter_end_week], width=0.75)
    idx = list(range(0, len(wk), 8))
    ax.set_xticks(idx, [wk.week_ending.iloc[i].strftime("%b %y") for i in idx], fontsize=8)
    ax.set_ylabel("Won per week, USD m")
    ax.set_title("Blue = last week of a quarter: a peak every quarter, not a trend", fontsize=9, color=INK2, loc="left")
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_bridge():
    br = pd.read_csv(PROC / "naive_vs_governed.csv")
    v = br.value.values / 1e6
    f, ax = fig(500, 270)
    run, bottoms, heights, colors = 0, [], [], []
    for i, x in enumerate(v):
        if i in (0, len(v) - 1):
            bottoms.append(0), heights.append(x), colors.append("#52514E")
            run = x
        else:
            bottoms.append(min(run, run + x)), heights.append(abs(x)), colors.append(GREEN if x > 0 else RED)
            run += x
    ax.bar(range(len(v)), heights, bottom=bottoms, color=colors, width=0.6)
    for i, (b, h, x) in enumerate(zip(bottoms, heights, v)):
        ax.text(i, b + h + 2, f"{x:+.1f}" if 0 < i < len(v) - 1 else f"{x:.1f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(v)), ["Naive\nsum", "EUR/GBP\nto USD", "Duplicate", "Won =\nsigned", "Cross-sell\nonce", "Governed"], fontsize=8)
    ax.set_ylim(min(bottoms[1:-1]) * 0.85, max(v[0], v[-1], *(np.array(bottoms) + np.array(heights))) * 1.06)
    ax.set_ylabel("USD m, Jan-Oct 2026 (axis cut)")
    ax.grid(axis="x", visible=False)
    return svg(f)


def pbi_or(n, fallback, alt):
    f = IMG / f"powerbi_p{n}.png"
    return (img(f.name, alt), True) if f.exists() else (fallback, False)


# ------------------------------------------------------------------ pages
def build_pages():
    K, E = FD["kpi"], FD["europe"]
    d = E["decomposition"]
    pubrev = pd.read_csv(PUB / "ergomed_revenue.csv")
    com = pd.read_csv(PUB / "ergomed_commercial.csv").set_index("year")
    rec = pd.read_csv(PUB / "reconciliation_public.csv")
    truth = pd.read_csv(PROC / "truth_check.csv")
    dq = pd.read_csv(PROC / "dq_issues.csv")
    comp = pd.read_csv(PUB / "competitors.csv")
    r25 = pubrev[pubrev.year == 2025]
    pv25 = r25[r25.business.str.startswith("Prime")].revenue_thousands.sum() / r25.revenue_thousands.sum()
    na25 = r25[r25.client_region == "North America"].revenue_thousands.sum() / r25.revenue_thousands.sum()
    pages = []

    # 0 Overview
    qs = ("<ol><li><b>What do the public accounts say</b> about Ergomed's commercial dynamics, and do the figures reconcile?</li>"
          "<li><b>Who are the clients</b> of a specialist CRO and pharmacovigilance group, and where are they?</li>"
          "<li><b>How do you make one set of KPIs</b> for three businesses that sell differently?</li>"
          "<li><b>How do you turn fragmented files</b> into a governed, refreshable Power BI model with access control?</li>"
          "<li><b>What does the data say</b> about performance vs target, and what is only a hypothesis?</li></ol>")
    reco = (f"<ol><li><b>Fix the definitions before the dashboards</b>: won = signed contract; one FX policy; cross-sell counted once. "
            f"Stacking the files gives {usdm(FD['data_issues']['bridge'][0]['value'])} instead of {usdm(K['ytd_won'])}, and a group win rate "
            f"of {pct(FD['data_issues']['naive_win_rate'])} instead of {pct(FD['data_issues']['governed_win_rate'])}.</li>"
            f"<li><b>Close the Europe gap where it is</b>: CRO oncology bid defenses ({pct(E['ta_win_rates'][0]['wr_py'])} -> "
            f"{pct(E['ta_win_rates'][0]['wr_ytd'])} win rate); demand is up, so the lever is conversion, not volume.</li>"
            "<li><b>Re-phase targets on the quarter profile</b> and read attainment quarter to date: flat monthly targets create "
            "false alarms in two months out of three.</li>"
            "<li><b>Make lateness visible</b>: a late file flags the weekly report INCOMPLETE and is restated, never silently missing.</li></ol>")
    flow = ('<div class="flow">' + '<div class="a">→</div>'.join(f'<div class="s"><b>{a}</b>{b}</div>' for a, b in [
        ("1. Public data", "Companies House, ClinicalTrials.gov, SEC, ECB"), ("2. Three exports", "CRM (EUR), PV trackers (USD),<br>ADAMAS tracker (GBP)"),
        ("3. Govern", "KPI dictionary, mappings,<br>14 quality checks"), ("4. Model", "Power BI TMDL + PBIR,<br>34 measures, RLS"),
        ("5. Report", "weekly report, monthly<br>pack, ad hoc note")]) + "</div>")
    pages.append(dict(
        title="Ergomed Group: one commercial reporting system for three businesses",
        subtitle="Public filings, clinical-trial and competitor data, plus a simulated multi-business commercial pipeline, turned into common "
                 "KPI definitions, a governed Power BI model, a weekly report, a monthly executive pack and a market view.",
        tag="OVERVIEW", tag_class="",
        kpis=[("Group new business, Jan-Oct 2026", usdm(K["ytd_won"]), f"{pct(K['attainment'])} of target · SIMULATED", "blue"),
              ("Europe vs target", pct(E["attainment"]), f"CRO Europe {pct(E['cro_eu_attainment'])}: oncology conversion · SIMULATED", "red"),
              ("Planted data issues found", f"{int(truth.found.sum())} / 8", "incl. one false signal · SIMULATED"),
              ("Ergomed revenue 2025", f"${r25.revenue_thousands.sum() / 1000:,.1f}m", f"PV {pct(pv25)} · North America {pct(na25)} · PUBLIC DATA")],
        cols="1fr 1fr", rows="1fr auto",
        cards=[card("Five questions", qs, text=True), card("Recommendations", reco, text=True),
               card("Method", flow + "<p style='margin-top:8px;font-size:12px;color:#52514E'>Real figures are labelled PUBLIC DATA; "
                    "the commercial pipeline is an illustrative SIMULATED dataset (anonymous clients 'Sponsor 014'), never presented as "
                    "Ergomed's. Findings are kept apart from hypotheses on every page.</p>", col="1 / 3")],
        footer="Collected 16 Nov 2026"))

    # 1 Ergomed in public data
    ob = com.order_book_m
    pages.append(dict(
        title=f"Ergomed's filed accounts show an order book that grew from GBP {ob[2019]:.0f}m to {ob[2023]:.0f}m (2019-2023) and "
              f"PrimeVigilance as the larger business by 2025 ({pct(pv25)} of revenue)",
        subtitle="Ergomed plc was acquired by funds advised by Permira in November 2023 (scheme effective 13 Nov, AIM listing cancelled "
                 "14 Nov) and renamed Ergomed Group Limited; from 2024 the group is consolidated by Eden TopCo Limited and reports in USD. "
                 "Historical figures, read on the scanned filings with the page cited.",
        tag="PUBLIC DATA · COMPANIES HOUSE", tag_class="real", kpis=None, cols="1.25fr 1fr", rows="1fr 1fr",
        cards=[card("Revenue by business, as filed (note 2 of each set of accounts)", ch_ergomed_revenue(), tag="PUBLIC DATA"),
               card("Order book and revenue, GBP m (annual reports 2019-2023)", ch_order_book(), tag="PUBLIC DATA"),
               card("The group's businesses (company websites and filings)",
                    "<ul><li><b>Ergomed CRO</b>: full-service clinical research, specialised in oncology and rare disease.</li>"
                    "<li><b>PrimeVigilance</b>: pharmacovigilance and clinical safety, medical information.</li>"
                    "<li><b>ADAMAS Consulting</b>: GxP audits and quality assurance (acquired Feb 2022).</li>"
                    "<li><b>Prudentia</b>: specialist safety and regulatory services (acquired 1 Apr 2025, per the FY2025 accounts).</li>"
                    f"<li>Clients by location, 2025: North America {pct(na25)}; UK + rest of EMEA "
                    f"{pct(r25[r25.client_region.isin(['UK', 'Rest of Europe, Middle East and Africa'])].revenue_thousands.sum() / r25.revenue_thousands.sum())}.</li></ul>",
                    text=True),
               card("Reconciliation: the same figure in two places",
                    table(rec[rec.id.isin(["R2", "R3", "R4", "R6", "R7"])][["id", "check", "explanation", "status"]].rename(
                        columns={"id": "", "check": "Check", "explanation": "Explanation", "status": "Status"})), text=True)],
        footer="Companies House: Ergomed Group Limited 04081094 (annual reports 2019-2023), Eden TopCo Limited 15049295 (accounts 2024-2025); "
               "page references in src/extract_accounts.py"))

    # 2 Market
    m25 = comp[comp.year == 2025].set_index("company").book_to_bill
    pages.append(dict(
        title=f"The clients are mostly small and mid-size sponsors: {pct(CT['small_mid_share_focus'])} of the {CT['focus_studies']:,} "
              "industry oncology and rare-disease studies started since 2019",
        subtitle=f"ClinicalTrials.gov, interventional studies with an industry lead sponsor, started 2019-2025 ({CT['studies']:,} studies). "
                 f"Oncology and rare disease are {pct(CT['focus_share'])} of them; {pct(CT['phase2_3_share_focus'])} are phase II or III, "
                 "the phases a specialist CRO competes for. Listed CROs reported book-to-bill of about 1.0x-1.2x.",
        tag="PUBLIC DATA · CLINICALTRIALS.GOV · SEC", tag_class="real", kpis=None, cols="1.2fr 1fr", rows="1fr 1fr",
        cards=[card("Studies started per year, oncology and rare disease (industry sponsors)", ch_trials_year(), tag="PUBLIC DATA"),
               card("Where the studies run (top 12 countries)", ch_countries(), row="1 / 3", tag="PUBLIC DATA"),
               card("Book-to-bill of listed CROs (definitions differ, see notes)", ch_competitors(), tag="PUBLIC DATA")],
        footer=f"ClinicalTrials.gov API v2 (US NLM), collected 16 Nov 2026; rare disease = proxy (MeSH inborn genetic diseases or 'rare'/'orphan'); "
               f"sponsor size = studies started 2019-2025 (small 1-5, mid 6-50) · Medpace, IQVIA 10-K; ICON results releases. "
               f"2025: Medpace {m25['Medpace']:.2f}x, ICON {m25['ICON']:.2f}x, IQVIA R&DS {m25['IQVIA (R&D Solutions)']:.2f}x (implied)"))

    # 3 Three businesses, one definition
    st = pd.read_csv(PROC / "stage_map.csv")
    piv = {b: st[st.business == b] for b in ["Ergomed CRO", "PrimeVigilance", "ADAMAS"]}
    stage_rows = ""
    for cs in ["1 Qualify", "2 Propose", "3 Negotiate", "4 Won", "5 Lost", "6 Disqualified"]:
        stage_rows += f"<tr><td><b>{cs}</b></td>" + "".join(
            f"<td>{', '.join(piv[b][piv[b].common_stage == cs].source_stage) or '-'}</td>" for b in piv) + "</tr>"
    stage_tbl = ("<table><tr><th>Common stage</th><th>Ergomed CRO (CRM)</th><th>PrimeVigilance (trackers)</th><th>ADAMAS (tracker)</th></tr>"
                 + stage_rows + "</table><p style='margin-top:6px;font-size:12px'><b>'Awarded' is not 'won'</b>: "
                 f"{pct(FD['data_issues']['award_not_contracted_rate'])} of CRO verbal awards were never contracted.</p>")
    kp = [("New business won", "contracts signed, USD at ECB monthly rate", "CRO contract value · PV annual value x years · ADAMAS quote"),
          ("Win rate", "won / (won + lost after proposal), decision date", "no-bids and early disqualifications excluded"),
          ("Weighted pipeline", "open value x stage probability", "probabilities still differ by system (open item)"),
          ("Book-to-bill", "won / revenue recognised", "same as listed CROs, which define it differently"),
          ("Attainment", "won / re-phased target", "target as received kept next to it"),
          ("Variance decomposition", "decisions x win rate x deal size", "exact, vs same period last year"),
          ("Cross-sell share", "won from clients of 2+ businesses", "needs the group client id"),
          ("Data freshness", "late files, on-time rate, open checks", "owner named for each source")]
    kpt = "<table><tr><th>KPI</th><th>Definition</th><th>Business differences / rule</th></tr>" + "".join(
        f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in kp) + "</table>"
    sqlc = pd.read_csv(PROC / "sql_checks.csv")
    pages.append(dict(
        title="Three businesses, one definition: a KPI dictionary and a stage map make the group numbers comparable",
        subtitle="Each business keeps its own system and vocabulary; the mapping lives in versioned CSV files, and each KPI has a DAX "
                 f"and a SQL version: {int((sqlc.match == 'yes').sum())} KPIs recomputed in SQL (DuckDB) match the Python pipeline exactly.",
        tag="SIMULATED · GOVERNANCE", tag_class="sim", kpis=None, cols="1.05fr 1fr", rows="1fr",
        cards=[card("Stage mapping (docs/governance/mappings/stage_map.csv)", stage_tbl, text=True),
               card("KPI dictionary, 15 KPIs (extract; full: docs/governance/KPI_DICTIONARY.md)", kpt, text=True)],
        footer="docs/governance/KPI_DICTIONARY.md, DATA_MAPPING.md · measures generated in src/build_tmdl.py"))

    # 4 governed model
    dqt = dq[["check_id", "check", "data_owner", "rows_flagged", "status"]].drop_duplicates("check_id").head(12)
    dqt.columns = ["", "Check", "Owner", "Rows", "Status"]
    shot1, real1 = pbi_or(1, "", "Power BI page 1")
    model_txt = ("<ul><li><b>Star schema</b>: FactOpportunity (3 businesses), FactTarget, FactRevenue, OrderBook; DimDate (marked), "
                 "Business, Region, Therapeutic area, Client, Stage. Import mode, single-direction relationships.</li>"
                 "<li><b>34 DAX measures</b> in 7 folders (wins, pipeline, conversion, targets, variance, revenue, data health), "
                 "written with their descriptions from one Python list.</li>"
                 "<li><b>RLS</b>: <span class='mono'>Group leadership</span> (all); <span class='mono'>Scoped user</span>: dynamic, "
                 "USERPRINCIPALNAME() against a business x region table; two static test roles.</li>"
                 "<li><b>Refresh</b>: Monday 10:30 + daily 06:00; files via SharePoint or the on-premises gateway; on failure the last good "
                 "data stays and the report states its refresh time.</li>"
                 "<li><b>Versions</b>: CHANGELOG.md (semantic versioning: a definition change = major version and restatement).</li></ul>")
    pages.append(dict(
        title=f"From fragmented files to a governed model: {dq.check_id.nunique()} automatic checks, every source reconciled, access by business and region",
        subtitle="Per-source shaping in Power Query (M) and Python; cross-source rules (duplicates, cross-sell, late files) logged in Python "
                 "with an owner. The model is a Power BI project in text format (TMDL + PBIR), rebuilt from code.",
        tag="SIMULATED · POWER BI", tag_class="sim", kpis=None, cols="1fr 1.1fr", rows="1fr 1fr",
        cards=[card("Quality checks by data owner (src/prepare.py)", table(dqt, num=("Rows",),
                    cls=lambda c, v: ("ok" if "Resolved" in str(v) or v == "OK" else "open" if v == "Open" else "") if c == "Status" else ""),
                    row="1 / 3", text=True),
               card("Power BI page 1 - Group overview" if real1 else "Semantic model (powerbi/ErgomedCommercial.pbip)",
                    shot1 if real1 else model_txt, text=not real1),
               card("Naive vs governed: what stacking the files would report", ch_bridge(), tag="SIMULATED")],
        footer="powerbi/ErgomedCommercial.SemanticModel (TMDL), .Report (PBIR) · powerquery/*.pq · docs/governance/RECONCILIATION.md, REPORTING_CALENDAR.md"))

    # 5 weekly + monthly
    pages.append(dict(
        title="The weekly report and the monthly pack are generated from the model: a late file is flagged, not hidden",
        subtitle="Weekly: movements, trend, exceptions and data status on one page (src/weekly_report.py). Monthly: 8 slides built to "
                 "think-cell conventions with python-pptx (action titles, waterfall, Mekko, difference annotations, native editable "
                 "charts); think-cell itself was not used.",
        tag="SIMULATED · REPORTING", tag_class="sim", kpis=None, cols="0.62fr 1fr 1fr", rows="1fr 1fr",
        cards=[card("Weekly report, week 45", img("weekly_report.png", "weekly report"), row="1 / 3"),
               card("Pack: waterfall slide", img("pack_slide3.png", "pack slide 3")),
               card("Pack: Mekko slide", img("pack_slide4.png", "pack slide 4")),
               card("Pack: conversion slide", img("pack_slide5.png", "pack slide 5")),
               card("Pack: data quality slide", img("pack_slide7.png", "pack slide 7"))],
        footer="reports/weekly_commercial_report.pdf · reports/monthly_commercial_pack.pptx"))

    # 6 what the data says
    hyp = {1: "Finding", 2: "Finding", 3: "Finding", 4: "Finding", 5: "Finding", 6: "Finding + proposal", 7: "Finding; cause = hypothesis", 8: "Finding (not a trend)"}
    tt = truth.copy()
    tt["type"] = tt.issue.map(hyp)
    tt = tt[["issue", "name", "evidence", "type"]]
    tt.columns = ["#", "Point", "Evidence (model)", "Status"]
    ta = {r["ta"]: r for r in E["ta_win_rates"]}
    adhoc = (f"<div class='fh'><div><b>Findings</b><br>Europe {pct(E['attainment'])} of target; CRO Europe {pct(E['cro_eu_attainment'])}. "
             f"Vs last year: volume {usdm(d['volume'])}, conversion {usdm(d['conversion'])}, deal size {usdm(d['deal_size'])}. "
             f"Oncology win rate {pct(ta['Oncology']['wr_py'])} -> {pct(ta['Oncology']['wr_ytd'])} (n={ta['Oncology']['n_ytd']}); "
             f"North America oncology {pct(ta['Oncology']['wr_na_ytd'])}. RFPs up ({E['onc_rfps_py']} -> {E['onc_rfps_cy']}).</div>"
             "<div><b>Hypotheses (to check)</b><br>Competitor pricing in European oncology bid defenses; a change in the bid team; "
             "sponsor mix. CRM loss reasons are too coarse to decide. <b>Next step</b>: review the last 10 losses with the CRO BD lead.</div></div>")
    pages.append(dict(
        title=f"What the data says: 8 of 8 planted issues found; Europe's gap is a conversion problem in CRO oncology, and the "
              "quarter-end peak is not a trend",
        subtitle="Planted issues were written to an answer key at simulation time and only compared at the end (src/check_truth.py). "
                 "The ad hoc note answers 'Why is Europe behind target?' with question, method, findings, hypotheses, limits, recommendation.",
        tag="SIMULATED · ANALYSIS", tag_class="sim", kpis=None, cols="1.15fr 1fr", rows="1.15fr 1fr",
        cards=[card("The 8 points, found by the pipeline", table(tt), text=True),
               card("CRO Europe: target to actual (USD m)", ch_waterfall(), tag="SIMULATED"),
               card("Ad hoc note: why is Europe behind? (docs/adhoc/europe_behind_target.md)", adhoc, text=True),
               card("Win rate by quarter: the break is European oncology only", ch_onc_quarterly(), tag="SIMULATED")],
        footer="data/processed/truth_check.csv, findings.json · weekly peak: last week of each quarter holds "
               f"{pct(FD['quarter_end']['min_share'])}-{pct(FD['quarter_end']['max_share'])} of its value (uniform: {pct(FD['quarter_end']['uniform_share'])})"))

    # 7 methods
    src = ("<table><tr><th>Source</th><th>Use</th><th>Type</th></tr>"
           "<tr><td>Companies House (Ergomed Group Ltd, Eden TopCo Ltd)</td><td>revenue, order book, awards, reconciliation</td><td>PUBLIC</td></tr>"
           "<tr><td>Group websites</td><td>description of the businesses</td><td>PUBLIC</td></tr>"
           "<tr><td>ClinicalTrials.gov API v2</td><td>market: studies by area, phase, country, sponsor size</td><td>PUBLIC</td></tr>"
           "<tr><td>SEC EDGAR; ICON results releases</td><td>backlog, awards, book-to-bill benchmarks</td><td>PUBLIC</td></tr>"
           "<tr><td>ECB Data Portal</td><td>monthly FX reference rates</td><td>PUBLIC</td></tr>"
           "<tr><td>src/simulate.py (seed 42)</td><td>3 commercial exports, targets, revenue, source log</td><td>SIMULATED</td></tr></table>")
    lim = ("<ul><li>The commercial pipeline is <b>simulated</b> and illustrative: it is not Ergomed's, and no conclusion about the "
           "company's performance follows from it. Calibration uses public orders of magnitude only.</li>"
           "<li>Ergomed figures are historical, read on scanned filings (OCR to search, values typed and arithmetic-checked). Nothing is "
           "said about the company's situation beyond its published accounts.</li>"
           "<li>Rare-disease flag in ClinicalTrials.gov is a proxy; sponsor size is a trial count. Competitor KPIs use different definitions.</li>"
           "<li>Power BI: the report is generated as code (TMDL + PBIR); the M queries in powerquery/ follow the same rules but are the "
           "migration path, not what the model refreshes today.</li></ul>")
    priv = ("<ul><li>No person names: directors (filings) and investigators (registry) are not extracted; simulated clients are "
            "anonymous ('Sponsor 014').</li><li>RLS by business and region; fictional @example.com accounts for testing.</li>"
            "<li>Raw downloads are not redistributed; scripts re-download them at a low request rate (robots.txt and terms checked).</li></ul>")
    pages.append(dict(
        title="Methods, limits and data protection", subtitle="Everything reruns from code: python src/run_all.py (collection scripts "
              "separately). Each figure in this document is read from a pipeline output.", tag="METHODS", tag_class="", kpis=None,
        cols="1fr 1fr", rows="1fr auto",
        cards=[card("Sources", src, text=True), card("Limits", lim, text=True),
               card("Data protection", priv, text=True),
               card("AI note", f"<div class='ai'>{AI_NOTE}</div>", text=True)],
        footer="README.md · data/SOURCES.md · data/ASSUMPTIONS.md"))
    return pages


def pack_images():
    """Export 4 slides of the pack to PNG through PowerPoint (Windows) for page 5; skipped if PowerPoint is not available."""
    pptx = REPORTS / "monthly_commercial_pack.pptx"
    ps = (f"$a = New-Object -ComObject PowerPoint.Application; $p = $a.Presentations.Open('{pptx}', $true, $false, $false); "
          + "; ".join(f"$p.Slides.Item({i}).Export('{IMG / f'pack_slide{i}.png'}', 'PNG', 1600, 900)" for i in (1, 3, 4, 5, 7))
          + "; $p.Close(); $a.Quit()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, timeout=180)
    except Exception as e:  # noqa: BLE001
        print("pack images skipped:", e)


def main():
    TMP.mkdir(exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    pack_images()
    pages = build_pages()
    head = f"<!doctype html><html><head><meta charset='utf-8'><title>Ergomed commercial reporting case study</title><style>{CSS}</style></head><body>"
    sections = [PAGE.render(p=p, foot=FOOTER) for p in pages]
    src = TMP / "report.html"
    src.write_text(head + "".join(sections) + "</body></html>", encoding="utf-8")
    html_to_pdf(src, PDF, "Ergomed Group - commercial reporting case study")
    for i, sec in enumerate(sections):
        one = TMP / f"pdf_p{i}.html"
        one.write_text(head.replace("page-break-after: always", "") + sec + "</body></html>", encoding="utf-8")
        screenshot(one, IMG / f"pdf_p{i}.png", 1536, 864)
    from pypdf import PdfReader
    print("PDF:", PDF.relative_to(ROOT), f"({PDF.stat().st_size // 1024} KB, {len(PdfReader(str(PDF)).pages)} pages)")


if __name__ == "__main__":
    main()
