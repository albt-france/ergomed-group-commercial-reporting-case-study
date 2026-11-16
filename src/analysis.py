"""Analyses on the governed model (SIMULATED data) -> data/processed/findings.json + small tables for the reports.

Every number used in a title of the PDF, the weekly report or the monthly pack comes from here.
Findings are kept apart from hypotheses: a 'finding' is what the data shows; a 'hypothesis' needs a check with a
data owner or the business before it is presented as a cause.

Periods: YTD = Jan-Oct 2026 (last closed month: October 2026); PY = Jan-Oct 2025; Q3 2026 = Jul-Sep 2026.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
f = pd.read_csv(P / "fact_opportunity.csv", parse_dates=["created_date", "proposal_date", "award_date", "won_date",
                                                          "lost_date", "decision_date", "cancel_date"])
t = pd.read_csv(P / "fact_target.csv", parse_dates=["month"])
rev = pd.read_csv(P / "fact_revenue.csv", parse_dates=["month"])
ob0 = pd.read_csv(P / "order_book_opening.csv")
YTD = ("2026-01-01", "2026-11-01")
PY = ("2025-01-01", "2025-11-01")
OCT = ("2026-10-01", "2026-11-01")
BUS = ["Ergomed CRO", "PrimeVigilance", "ADAMAS"]
REG = ["Europe", "North America", "Asia-Pacific", "Rest of World"]


def between(s, p):
    return (s >= p[0]) & (s < p[1])


won = f[f.status == "Won"]


def won_value(p, **flt):
    w = won[between(won.won_date, p)]
    for k, v in flt.items():
        w = w[w[k] == v]
    return w.value_usd_governed.sum()


def target(p, col="target_phased_usd", **flt):
    x = t[between(t.month, p)]
    for k, v in flt.items():
        x = x[x[k] == v]
    return x[col].sum()


def decomp(p_cy, p_py, **flt):
    """Won value = decisions x win rate x average won value. Sequential substitution, exact:
    volume = (N1-N0) WR0 A0 ; conversion = N1 (WR1-WR0) A0 ; deal size = N1 WR1 (A1-A0)."""
    out = {}
    for k, p in (("cy", p_cy), ("py", p_py)):
        d = f[f.in_win_rate & between(f.decision_date, p)]
        for kk, v in flt.items():
            d = d[d[kk] == v]
        n = len(d)
        w = d[d.status == "Won"]
        out[k] = (n, len(w) / n if n else 0, w.value_usd_governed.mean() if len(w) else 0, w.value_usd_governed.sum())
    (n1, r1, a1, v1), (n0, r0, a0, v0) = out["cy"], out["py"]
    return dict(py=v0, volume=(n1 - n0) * r0 * a0, conversion=n1 * (r1 - r0) * a0, deal_size=n1 * r1 * (a1 - a0), cy=v1,
                n_cy=n1, n_py=n0, wr_cy=r1, wr_py=r0, avg_cy=a1, avg_py=a0)


def win_rate(p, **flt):
    d = f[f.in_win_rate & between(f.decision_date, p)]
    for k, v in flt.items():
        d = d[d[k] == v]
    return (d.status == "Won").mean() if len(d) else np.nan, len(d)


def main():
    F = {}
    # ---------------- headline KPIs
    ytd_won, ytd_t, ytd_tf = won_value(YTD), target(YTD), target(YTD, "target_flat_usd")
    rev_ytd = rev[between(rev.month, YTD)].revenue_usd.sum()
    open_ = f[f.status == "Open"]
    F["kpi"] = dict(ytd_won=ytd_won, ytd_target=ytd_t, attainment=ytd_won / ytd_t, attainment_flat=ytd_won / ytd_tf,
                    py_won=won_value(PY), growth=ytd_won / won_value(PY) - 1, revenue_ytd=rev_ytd, book_to_bill=ytd_won / rev_ytd,
                    open_pipeline=open_.value_usd_governed.sum(), weighted_pipeline=open_.weighted_value_usd.sum(),
                    win_rate=win_rate(YTD)[0], win_rate_py=win_rate(PY)[0],
                    oct_won=won_value(OCT), oct_target=target(OCT), oct_target_flat=target(OCT, "target_flat_usd"))
    # by business and region
    F["by_business"] = {b: dict(won=won_value(YTD, business=b), target=target(YTD, business=b),
                                py=won_value(PY, business=b), revenue=rev[between(rev.month, YTD) & (rev.business == b)].revenue_usd.sum(),
                                win_rate=win_rate(YTD, business=b)[0], win_rate_py=win_rate(PY, business=b)[0])
                        for b in BUS}
    F["by_region"] = {r: dict(won=won_value(YTD, region=r), target=target(YTD, region=r), py=won_value(PY, region=r))
                      for r in REG}
    F["by_business_region"] = [dict(business=b, region=r, won=won_value(YTD, business=b, region=r),
                                    target=target(YTD, business=b, region=r)) for b in BUS for r in REG]

    # ---------------- issue 7: Europe behind target -> CRO Europe -> oncology conversion
    eu = F["by_region"]["Europe"]
    cro_eu = decomp(YTD, PY, business="Ergomed CRO", region="Europe")
    cro_na = decomp(YTD, PY, business="Ergomed CRO", region="North America")
    ta_wr = []
    for ta in ["Oncology", "Rare disease", "CNS", "Immunology", "Other"]:
        a, na = win_rate(PY, business="Ergomed CRO", region="Europe", therapeutic_area=ta)
        b, nb = win_rate(YTD, business="Ergomed CRO", region="Europe", therapeutic_area=ta)
        c, nc = win_rate(YTD, business="Ergomed CRO", region="North America", therapeutic_area=ta)
        ta_wr.append(dict(ta=ta, wr_py=a, n_py=na, wr_ytd=b, n_ytd=nb, wr_na_ytd=c, n_na_ytd=nc))
    q = []
    for qs in pd.period_range("2025Q1", "2026Q3", freq="Q"):
        p = (str(qs.start_time.date()), str((qs.end_time + pd.Timedelta(days=1)).date()))
        q.append(dict(quarter=str(qs), onc_eu=win_rate(p, business="Ergomed CRO", region="Europe", therapeutic_area="Oncology")[0],
                      onc_na=win_rate(p, business="Ergomed CRO", region="North America", therapeutic_area="Oncology")[0],
                      rare_eu=win_rate(p, business="Ergomed CRO", region="Europe", therapeutic_area="Rare disease")[0],
                      onc_eu_n=win_rate(p, business="Ergomed CRO", region="Europe", therapeutic_area="Oncology")[1]))
    pd.DataFrame(q).to_csv(P / "an_oncology_quarterly.csv", index=False)
    # volume of RFPs and proposal value for oncology Europe: did demand change?
    onc = f[(f.business == "Ergomed CRO") & (f.region == "Europe") & (f.therapeutic_area == "Oncology")]
    rfp_py = (between(onc.created_date, PY)).sum()
    rfp_cy = (between(onc.created_date, YTD)).sum()
    lost_onc = onc[(onc.status == "Lost") & between(onc.decision_date, YTD)]
    F["europe"] = dict(attainment=eu["won"] / eu["target"], gap=eu["won"] - eu["target"],
                       cro_eu_attainment=won_value(YTD, business="Ergomed CRO", region="Europe") / target(YTD, business="Ergomed CRO", region="Europe"),
                       cro_eu_gap=won_value(YTD, business="Ergomed CRO", region="Europe") - target(YTD, business="Ergomed CRO", region="Europe"),
                       decomposition=cro_eu, decomposition_na=cro_na, ta_win_rates=ta_wr,
                       onc_rfps_py=int(rfp_py), onc_rfps_cy=int(rfp_cy),
                       onc_avg_value_py=float(onc[between(onc.created_date, PY)].value_usd.mean()),
                       onc_avg_value_cy=float(onc[between(onc.created_date, YTD)].value_usd.mean()),
                       onc_loss_reasons=lost_onc.loss_reason.value_counts().to_dict(),
                       target_cro_eu=target(YTD, business="Ergomed CRO", region="Europe"))
    # waterfall target -> actual (CRO Europe): target, growth assumed by the plan, volume, conversion, deal size, actual
    d = cro_eu
    wf = pd.DataFrame([("Target YTD", F["europe"]["target_cro_eu"]), ("Growth assumed in target", d["py"] - F["europe"]["target_cro_eu"]),
                       ("Volume (decisions)", d["volume"]), ("Conversion (win rate)", d["conversion"]),
                       ("Deal size", d["deal_size"]), ("Actual YTD", d["cy"])], columns=["step", "value"])
    wf.to_csv(P / "an_waterfall_cro_europe.csv", index=False)

    # ---------------- issue 6: flat vs phased targets
    m = []
    for mo in pd.period_range("2026-01", "2026-10", freq="M"):
        p = (str(mo.start_time.date()), str((mo.end_time + pd.Timedelta(days=1)).date()))
        m.append(dict(month=str(mo), won=won_value(p), target_flat=target(p, "target_flat_usd"), target_phased=target(p)))
    m = pd.DataFrame(m)
    m["att_flat"], m["att_phased"] = m.won / m.target_flat, m.won / m.target_phased
    m.to_csv(P / "an_monthly_target.csv", index=False)
    qe = m.month.str[-2:].isin(["03", "06", "09"])
    wq = won[between(won.won_date, ("2025-01-01", "2026-10-01"))].copy()
    wq["q"], wq["miq"] = wq.won_date.dt.to_period("Q"), (wq.won_date.dt.month - 1) % 3 + 1
    prof = wq.groupby(["q", "miq"]).value_usd_governed.sum().unstack()
    prof = prof.div(prof.sum(axis=1), axis=0)
    qatt = []
    for qq in pd.period_range("2026Q1", "2026Q3", freq="Q"):
        p = (str(qq.start_time.date()), str((qq.end_time + pd.Timedelta(days=1)).date()))
        qatt.append(dict(quarter=str(qq), won=won_value(p), target=target(p), attainment=won_value(p) / target(p)))
    F["phasing"] = dict(months_below_90_flat=int((m.att_flat < 0.9).sum()), months_below_90_phased=int((m.att_phased < 0.9).sum()),
                        mid_quarter_att_flat=float(m[~qe].won.sum() / m[~qe].target_flat.sum()),
                        mid_quarter_att_phased=float(m[~qe].won.sum() / m[~qe].target_phased.sum()),
                        qe_att_flat=float(m[qe].won.sum() / m[qe].target_flat.sum()),
                        m3_share_avg=float(prof[3].mean()), m3_share_min=float(prof[3].min()), m3_share_max=float(prof[3].max()),
                        m1_share_avg=float(prof[1].mean()), quarters=qatt)

    # ---------------- issue 8: quarter-end spike (false signal)
    w = won.copy()
    w["week"] = w.won_date + pd.to_timedelta(6 - w.won_date.dt.day_of_week, unit="D")
    wk = w[between(w.won_date, ("2025-01-01", "2026-11-09"))].groupby("week").value_usd_governed.sum()
    wk = wk.reindex(pd.date_range("2025-01-05", "2026-11-08", freq="W-SUN"), fill_value=0)
    qe_week = pd.Series((wk.index + pd.offsets.QuarterEnd(0) - wk.index).days < 7, index=wk.index) | \
        pd.Series(((wk.index - pd.Timedelta(days=6)) + pd.offsets.QuarterEnd(0) <= wk.index), index=wk.index)
    wkdf = pd.DataFrame({"week_ending": wk.index.date, "won_usd": wk.values, "quarter_end_week": qe_week.values})
    wkdf.to_csv(P / "an_weekly_won.csv", index=False)
    share = []
    for qq, g in w[between(w.won_date, ("2025-01-01", "2026-10-01"))].groupby(w.won_date.dt.to_period("Q")):
        last = g.won_date >= (qq.end_time.normalize() - pd.Timedelta(days=6))
        share.append(dict(quarter=str(qq), last_week_share=g[last].value_usd_governed.sum() / g.value_usd_governed.sum()))
    share = pd.DataFrame(share)
    share.to_csv(P / "an_quarter_end_share.csv", index=False)
    sep = wkdf[wkdf.week_ending.astype(str).between("2026-09-27", "2026-10-04")].won_usd.max()
    F["quarter_end"] = dict(avg_last_week_share=float(share.last_week_share.mean()), min_share=float(share.last_week_share.min()),
                            max_share=float(share.last_week_share.max()), uniform_share=1 / 13,
                            sep_2026_peak_week=float(sep), median_week=float(wkdf.won_usd.median()),
                            q3_2026_share=float(share[share.quarter == "2026Q3"].last_week_share.iloc[0]))

    # ---------------- issues 1-5: data issues, quantified from the prep outputs
    bridge = pd.read_csv(P / "naive_vs_governed.csv")
    dqi = pd.read_csv(P / "dq_issues.csv")
    health = pd.read_csv(P / "data_health.csv")
    s = json.loads((P / "prep_summary.json").read_text())
    cro = f[f.business == "Ergomed CRO"]
    awards = cro[cro.award_date.notna() & (cro.award_date < "2026-08-01")]
    F["data_issues"] = dict(bridge=bridge.to_dict("records"), naive_win_rate=s["naive_win_rate"], governed_win_rate=s["governed_win_rate"],
                            award_not_contracted_rate=float((awards.loss_reason == "Award not contracted").mean()),
                            cross_sell_pairs=s["cross_sell_pairs"],
                            cross_sell_value=float(-f.cross_sell_adj_usd.sum()),
                            duplicate_value=float(-bridge.loc[bridge.step.str.contains("duplicate"), "value"].iloc[0]),
                            fx_effect=float(bridge.loc[bridge.step.str.contains("Convert"), "value"].iloc[0]),
                            late_source=health[health.status == "LATE"][["data_owner", "received", "deadline", "impact"]].to_dict("records"),
                            dq_open=int((dqi.status == "Open").sum()), dq_checks=int(dqi.check_id.nunique()))
    # cross-sell share (clients won in 2+ businesses)
    cl = pd.read_csv(P / "dim_client.csv")
    multi = set(cl[cl.multi_business_client].group_client_id)
    wy = won[between(won.won_date, YTD)]
    F["kpi"]["cross_sell_share"] = float(wy[wy.group_client_id.isin(multi)].value_usd_governed.sum() / wy.value_usd_governed.sum())
    # order book roll-forward (YTD)
    ob = []
    for b in BUS:
        o = ob0.loc[ob0.business == b, "order_book_usd"].iloc[0]
        wb = won[(won.business == b)]
        rb = rev[rev.business == b]
        canc = f[(f.business == b) & f.cancel_date.notna()]
        for mo in pd.period_range("2024-11", "2026-10", freq="M"):
            p = (str(mo.start_time.date()), str((mo.end_time + pd.Timedelta(days=1)).date()))
            add = wb[between(wb.won_date, p)].value_usd_governed.sum()
            rv = rb[between(rb.month, p)].revenue_usd.sum()
            cn = canc[between(canc.cancel_date, p)].value_usd_governed.sum()
            o = o + add - rv - cn
            ob.append(dict(business=b, month=mo.start_time.date(), won=add, revenue=rv, cancelled=cn, closing_order_book=o))
    ob = pd.DataFrame(ob)
    ob.to_csv(P / "an_order_book.csv", index=False)
    F["kpi"]["order_book"] = float(ob[ob.month == pd.Timestamp("2026-10-01").date()].closing_order_book.sum())
    F["kpi"]["order_book_open"] = float(ob0.order_book_usd.sum())

    # pipeline by stage x business (funnel) and cycle time
    fun = f[between(f.created_date, ("2025-01-01", "2026-11-01"))]
    stages = []
    for b in BUS:
        x = fun[fun.business == b]
        stages.append(dict(business=b, created=len(x), reached_proposal=int(x.reached_proposal.sum()),
                           reached_negotiate=int((x.common_stage.isin(["3 Negotiate", "4 Won"]) | (x.status == "Won")).sum() +
                                                 ((x.status == "Lost") & x.award_date.notna()).sum()),
                           won=int((x.status == "Won").sum()), cycle_days=float(f[(f.business == b) & (f.status == "Won") &
                                                                                   between(f.won_date, YTD)].cycle_days.median())))
    pd.DataFrame(stages).to_csv(P / "an_funnel.csv", index=False)
    F["funnel"] = stages
    (P / "findings.json").write_text(json.dumps(F, indent=2, default=float))
    k = F["kpi"]
    print(f"YTD won ${k['ytd_won'] / 1e6:.1f}m vs target ${k['ytd_target'] / 1e6:.1f}m ({k['attainment']:.0%}; flat {k['attainment_flat']:.0%}),"
          f" BtB {k['book_to_bill']:.2f}, win rate {k['win_rate']:.0%} (PY {k['win_rate_py']:.0%})")
    print(f"Europe {F['europe']['attainment']:.0%}, CRO Europe {F['europe']['cro_eu_attainment']:.0%};",
          {kk: round(v / 1e6, 1) for kk, v in cro_eu.items() if kk in ("py", "volume", "conversion", "deal_size", "cy")})
    print("TA win rates Europe:", [(r['ta'], round(r['wr_py'], 2), round(r['wr_ytd'], 2), r['n_ytd']) for r in ta_wr])
    print("phasing:", {kk: round(v, 2) for kk, v in F["phasing"].items() if kk != "quarters"}, "| QE share:", {kk: round(v, 3) for kk, v in F["quarter_end"].items()})


if __name__ == "__main__":
    main()
