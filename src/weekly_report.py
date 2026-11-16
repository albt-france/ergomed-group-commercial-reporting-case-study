"""Weekly commercial report (one page, A4), generated from the governed model - SIMULATED data.

Week 45 = Mon 2 - Sun 8 Nov 2026. Deadline for source files: Mon 9 Nov 10:00 (docs/governance/REPORTING_CALENDAR.md).
The report reads data/processed (src/prepare.py) and the source log: any source received after the deadline is
printed as an exception at the top, with what it changes. Nothing is typed by hand.

Usage: python src/weekly_report.py  -> reports/weekly_commercial_report.pdf (+ .html, docs/img/weekly_report.png)
"""
import json

import pandas as pd

from common import (BLUE, BUS_COLORS, FOOTER, GRAY, IMG, INK2, PROC, REPORTS, RED, ROOT, TMP, html_to_pdf, mpl, pct,
                    screenshot, svg, usdm)

WEEK = (pd.Timestamp("2026-11-02"), pd.Timestamp("2026-11-08"))
PREV_END = WEEK[0] - pd.Timedelta(days=1)
QTD = (pd.Timestamp("2026-10-01"), WEEK[1])
BUS = ["Ergomed CRO", "PrimeVigilance", "ADAMAS"]

f = pd.read_csv(PROC / "fact_opportunity.csv", parse_dates=["created_date", "proposal_date", "won_date", "decision_date", "award_date"])
t = pd.read_csv(PROC / "fact_target.csv", parse_dates=["month"])
health = pd.read_csv(PROC / "data_health.csv")
dq = pd.read_csv(PROC / "dq_issues.csv")
late_raw = pd.read_csv(ROOT / "data" / "simulated" / "pv_pipeline_na_late.csv", parse_dates=["signed_on"])


def inwk(s, a=WEEK[0], b=WEEK[1]):
    return (s >= a) & (s <= b)


def open_at(d):
    return f[(f.created_date <= d) & (f.decision_date.isna() | (f.decision_date > d))]


def main():
    won = f[(f.status == "Won") & inwk(f.won_date)]
    w13 = f[(f.status == "Won") & inwk(f.won_date, WEEK[0] - pd.Timedelta(weeks=13), PREV_END)]
    rows = []
    for b in BUS:
        o1, o0 = open_at(WEEK[1]), open_at(PREV_END)
        rows.append(dict(business=b, won=won[won.business == b].value_usd_governed.sum(), deals=(won.business == b).sum(),
                         avg13=w13[w13.business == b].value_usd_governed.sum() / 13,
                         created=((f.business == b) & inwk(f.created_date)).sum(),
                         proposals=((f.business == b) & inwk(f.proposal_date)).sum(),
                         lost=((f.business == b) & (f.status == "Lost") & inwk(f.decision_date)).sum(),
                         wpipe=o1[o1.business == b].weighted_value_usd.sum(), pipe_prev=o0[o0.business == b].weighted_value_usd.sum()))
    tb = pd.DataFrame(rows)
    tot = tb.sum(numeric_only=True)

    # quarter to date vs re-phased target (November prorated by days elapsed)
    qwon = f[(f.status == "Won") & inwk(f.won_date, *QTD)].value_usd_governed.sum()
    t_oct = t[t.month == "2026-10-01"].target_phased_usd.sum()
    t_nov = t[t.month == "2026-11-01"].target_phased_usd.sum()
    t_q4 = t[t.month.between("2026-10-01", "2026-12-01")].target_phased_usd.sum()
    expected_now = t_oct + t_nov * 8 / 30

    # late source: what the Monday version missed
    late = health[health.status == "LATE"]
    late_new = late_raw[late_raw.signed_on.between(WEEK[0], WEEK[1])]
    banner = ""
    if len(late):
        r = late.iloc[0]
        banner = (f"<div class='banner'><b>Exception - late source.</b> {r.data_owner} ({r.source_file}) was received "
                  f"{pd.Timestamp(r.received):%a %d %b %H:%M}, after the deadline ({pd.Timestamp(r.deadline):%a %d %b %H:%M}). "
                  f"The Monday version was flagged INCOMPLETE and excluded {len(late_new)} signed PV deals "
                  f"({usdm(late_new.tcv_usd.sum())}). This version (restated {pd.Timestamp('2026-11-11 16:00'):%a %d %b %H:%M}) includes them.</div>")

    top = won.sort_values("value_usd_governed", ascending=False).head(5)
    top_rows = "".join(f"<tr><td>{r.client_name}</td><td>{r.business}</td><td>{r.region}</td><td>{r.therapeutic_area if r.business != 'ADAMAS' else r.detail}</td>"
                       f"<td class='n'>{usdm(r.value_usd_governed, 2)}</td></tr>" for r in top.itertuples())

    # exceptions and points of attention
    fd = json.loads((PROC / "findings.json").read_text())
    onc = pd.read_csv(PROC / "an_oncology_quarterly.csv")
    q3 = onc[onc.quarter == "2026Q3"].iloc[0]
    q1_25 = onc[onc.quarter.str.startswith("2025")].onc_eu.mean()
    open_dq = dq[dq.status == "Open"]
    verbal = f[f.verbal_award_open]
    exc = [f"<li><b>CRO Europe, oncology:</b> win rate {pct(q3.onc_eu)} in Q3 2026 vs {pct(q1_25)} on average in 2025 "
           f"(North America oncology: {pct(q3.onc_na)}). Main reason CRO Europe is at {pct(fd['europe']['cro_eu_attainment'])} of target YTD. "
           "Ad hoc note: docs/adhoc/europe_behind_target.md.</li>",
           f"<li><b>Verbal awards not yet contracted:</b> {len(verbal)} CRO opportunities ({usdm(verbal.value_usd_governed.sum())}) "
           "are counted as open, not won, until the contract is signed.</li>",
           f"<li><b>Data quality:</b> {open_dq.check_id.nunique()} checks open - "
           + "; ".join(f"{cid} {g.data_owner.iloc[0]} ({g.rows_flagged.sum()} rows)" for cid, g in open_dq.groupby("check_id", sort=False))
           + ". Owners and actions: Data health page of the Power BI report.</li>"]
    biggest = won[won.business == tb.loc[tb.won.idxmax(), "business"]]
    att = [f"<li>This week: {usdm(tot['won'])}, {tot['won'] / tot['avg13']:.1f}x the 13-week average, mostly "
           f"{tb.loc[tb.won.idxmax(), 'business']} ({len(biggest)} contracts, largest {usdm(biggest.value_usd_governed.max())}). "
           "One week is timing, not a trend.</li>",
           f"<li>Quarter to date: {usdm(qwon)} won vs {usdm(expected_now)} expected by now on the re-phased target "
           f"({pct(qwon / expected_now)}); full Q4 target {usdm(t_q4)}. Most of a quarter is signed in its last weeks: "
           "no conclusion on Q4 before mid-December.</li>",
           f"<li>Weighted pipeline {usdm(tot["wpipe"])} ({'+' if tot["wpipe"] >= tot["pipe_prev"] else ''}{usdm(tot["wpipe"] - tot["pipe_prev"])} on the week).</li>"]

    # chart: weekly won value, last 26 weeks, quarter-end weeks marked
    wk = pd.read_csv(PROC / "an_weekly_won.csv", parse_dates=["week_ending"]).tail(26)
    plt = mpl()
    fig, ax = plt.subplots(figsize=(7.4, 1.9), dpi=96)
    ax.bar(range(len(wk)), wk.won_usd / 1e6, color=[BLUE if q else GRAY for q in wk.quarter_end_week], width=0.7)
    ax.set_xticks(range(0, len(wk), 4), [d.strftime("%d %b") for d in wk.week_ending.iloc[::4]])
    ax.set_ylabel("USD m")
    ax.set_title("New business won per week (blue = last week of a quarter: the usual signing peak)", fontsize=9, color=INK2, loc="left")
    chart = svg(fig)

    trs = "".join(f"<tr><td><span class='dot' style='background:{BUS_COLORS[r.business]}'></span>{r.business}</td>"
                  f"<td class='n'><b>{usdm(r.won)}</b></td><td class='n'>{r.deals}</td><td class='n'>{usdm(r.avg13)}</td>"
                  f"<td class='n'>{r.created}</td><td class='n'>{r.proposals}</td><td class='n'>{r.lost}</td>"
                  f"<td class='n'>{usdm(r.wpipe)}</td><td class='n {'neg' if r.wpipe < r.pipe_prev else ''}'>{usdm(r.wpipe - r.pipe_prev)}</td></tr>"
                  for r in tb.itertuples())
    trs += (f"<tr class='tot'><td>Group</td><td class='n'>{usdm(tot.won)}</td><td class='n'>{int(tot.deals)}</td><td class='n'>{usdm(tot.avg13)}</td>"
            f"<td class='n'>{int(tot.created)}</td><td class='n'>{int(tot.proposals)}</td><td class='n'>{int(tot.lost)}</td>"
            f"<td class='n'>{usdm(tot["wpipe"])}</td><td class='n'>{usdm(tot["wpipe"] - tot["pipe_prev"])}</td></tr>")

    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Weekly commercial report - week 45</title><style>
@page {{ size: A4; margin: 0 }}
* {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{ font-family: 'Segoe UI', sans-serif; color: #0B0B0B; background: #F4F4F2; font-size: 11px }}
.page {{ width: 794px; height: 1122px; padding: 26px 30px; display: flex; flex-direction: column; gap: 9px; overflow: hidden }}
h1 {{ font-size: 19px }} .sub {{ color: #52514E; font-size: 11.5px }} .tag {{ float: right; font-size: 9.5px; font-weight: 700; color: #1C5CAB;
 border: 1px solid #86B6EF; border-radius: 4px; padding: 2px 7px; background: #FCFCFB }}
.banner {{ background: #FBEAEA; border-left: 4px solid {RED}; padding: 7px 10px; font-size: 11px; border-radius: 4px }}
.card {{ background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 7px; padding: 9px 12px }}
.card h3 {{ font-size: 12px; margin-bottom: 5px }}
table {{ border-collapse: collapse; width: 100% }} th {{ text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #C9C7BF; padding: 3px 4px; font-size: 10px }}
td {{ padding: 3px 4px; border-bottom: 1px solid #EEEDE8; white-space: nowrap }} .n {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }}
tr.tot td {{ font-weight: 700; background: #F4F4F2 }} .neg {{ color: {RED} }}
.dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px }}
ul {{ margin-left: 16px }} li {{ white-space: normal;  margin-bottom: 3px; line-height: 1.35 }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 9px }}
.fal {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 9px; font-size: 10.2px }} .fal b {{ display: block; color: #1C5CAB; margin-bottom: 2px }}
.chart {{ height: 150px }} footer {{ margin-top: auto; font-size: 9px; color: #898781 }}
</style></head><body><section class='page'>
<div><span class='tag'>SIMULATED · ILLUSTRATIVE DATASET</span><h1>Weekly commercial report - week 45 (2-8 Nov 2026)</h1>
<p class='sub'>Group view, three businesses, USD at ECB monthly rates. Generated automatically from the governed model (src/weekly_report.py).</p></div>
{banner}
<div class='card'><h3>Key movements this week</h3><table><tr><th>Business</th><th class='n'>Won</th><th class='n'>Deals</th>
<th class='n'>13-wk avg / week</th><th class='n'>Created</th><th class='n'>Proposals</th><th class='n'>Lost</th><th class='n'>Weighted pipeline</th>
<th class='n'>Change</th></tr>{trs}</table></div>
<div class='card chart'>{chart}</div>
<div class='grid'><div class='card'><h3>Largest wins this week</h3><table><tr><th>Client</th><th>Business</th><th>Region</th><th>Area / type</th>
<th class='n'>Value</th></tr>{top_rows}</table></div>
<div class='card'><h3>Trend and points of attention</h3><ul>{''.join(att)}</ul></div></div>
<div class='card'><h3>Exceptions</h3><ul>{''.join(exc)}</ul></div>
<div class='card fal'><div><b>Findings</b>Figures above are computed from the three source files after mapping, conversion and quality
checks; the late PV North America file is included in this restated version.</div>
<div><b>Assumptions</b>Won = signed contract (CRO 'Awarded' is not a win). PV value = annual value x years. November uses the last
published ECB rate (provisional). Q4 'expected by now' prorates November by days.</div>
<div><b>Limitations</b>Simulated, illustrative data, not Ergomed's pipeline. One week is a small sample: weekly swings are
mostly timing; use the quarter view for performance.</div></div>
<footer>Sources: cro_crm.xlsx, pv_pipeline.csv (+ North America late file), adamas_tracker.xlsx, targets.xlsx, revenue_actuals.csv
(all SIMULATED) · {FOOTER}</footer></section></body></html>"""
    TMP.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    src = TMP / "weekly_report.html"
    src.write_text(html, encoding="utf-8")
    html_to_pdf(src, REPORTS / "weekly_commercial_report.pdf", "Weekly commercial report - week 45 (simulated data)")
    screenshot(src, IMG / "weekly_report.png", 794, 1122)
    print(f"week 45: won {usdm(tot.won)} ({int(tot.deals)} deals), QTD {usdm(qwon)} vs expected {usdm(expected_now)}, late source: {len(late)}")


if __name__ == "__main__":
    main()
