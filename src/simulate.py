"""SIMULATED - illustrative commercial dataset for a three-business group (NOT Ergomed's pipeline).

Writes the raw exports a commercial analyst would receive, deliberately different from each other, as in a group
built through acquisitions (seed 42, 24 months: Nov 2024 - Oct 2026, plus the first week of Nov 2026):

  data/simulated/cro_crm.xlsx           Ergomed CRO opportunities (CRM export), values in EUR, RFP/bid-defense stages
  data/simulated/pv_pipeline.csv        PrimeVigilance contracts (recurring), USD, other stage names, compiled from 3
                                        regional trackers; pv_pipeline_na_late.csv = the North America file sent late
  data/simulated/adamas_tracker.xlsx    ADAMAS audit engagements, GBP, manual tracker with merged cells
  data/simulated/targets.xlsx           new-business targets by business x region x month (annual / 12, as received)
  data/simulated/revenue_actuals.csv    recognised revenue by business x region x month (finance, USD)
  data/simulated/order_book_opening.csv contracted order book at 31 Oct 2024 (finance, USD)
  data/simulated/clients_master.csv     one group client id, a different client code per business
  data/simulated/source_log.csv         weekly submissions: owner, deadline, received timestamp, rows
  data/_hidden_truth.csv                the 8 planted issues (answer key, used only at the end by src/check_truth.py)

Calibration (orders of magnitude only, see data/ASSUMPTIONS.md): business mix and client regions from the group's
filed accounts (North America ~60% of revenue, PV slightly larger than CRO); book-to-bill around 1.1-1.2 as for
listed CROs (data/public/competitors.csv). Clients are anonymous ('Sponsor 014'); no person names anywhere.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "simulated"
rng = np.random.default_rng(42)

START, END = pd.Timestamp("2024-03-01"), pd.Timestamp("2026-11-08")   # creation window / data cut (end of week 45)
REGIONS = ["Europe", "North America", "Asia-Pacific", "Rest of World"]
REGION_W = np.array([0.33, 0.54, 0.08, 0.05])
COUNTRIES = {
    "Europe": ["United Kingdom", "Germany", "France", "Spain", "Italy", "Netherlands", "Switzerland", "Croatia",
               "Poland", "Sweden", "Belgium", "Denmark"],
    "North America": ["United States", "United States", "United States", "United States", "Canada"],
    "Asia-Pacific": ["Japan", "South Korea", "Australia", "China", "Singapore", "India"],
    "Rest of World": ["Israel", "Brazil", "South Africa", "Turkey", "Mexico"],
}
CRO_REGION_CODE = {"Europe": "EU", "North America": "NA", "Asia-Pacific": "APAC", "Rest of World": "ROW"}
ADAMAS_REGION = {"Europe": "EMEA", "North America": "Americas", "Asia-Pacific": "Asia", "Rest of World": "EMEA"}
FX = pd.read_csv(ROOT / "data" / "public" / "fx_rates_ecb.csv").pivot(index="month", columns="currency", values="rate_to_usd")


def fx(d, ccy):
    """ECB monthly average of the month; a month not yet published uses the last published month (provisional)."""
    m = min(pd.Timestamp(d).strftime("%Y-%m"), FX.index.max())
    return FX.loc[m, ccy]


def bdays(a, b):
    return pd.bdate_range(a, b)


def qend_pull(d, p):
    """Sponsors sign at quarter end (budget cycles): a decision due within 45 days of quarter end is pulled to the
    last week of the quarter with probability p; August decisions slip to early September (p=0.35). This is the normal
    seasonality behind planted issues 6 (flat targets) and 8 (quarter-end 'spike')."""
    if d.month == 8 and rng.random() < 0.35:                         # August: decisions slip to September
        d = bdays(pd.Timestamp(d.year, 9, 1), pd.Timestamp(d.year, 9, 15))[int(rng.integers(10))]
    qe = d + pd.offsets.QuarterEnd(0)
    if (qe - d).days <= 45 and rng.random() < p:
        last = bdays(qe - pd.Timedelta(days=6), qe)
        return last[rng.integers(len(last))]
    return d


def ch(spec):
    return str(rng.choice(spec[0], p=spec[1]))


def add(d, lo, hi):
    return d + pd.Timedelta(days=int(rng.integers(lo, hi + 1)))


# ------------------------------------------------------------------ clients
N_CLIENTS = 260
clients = pd.DataFrame({"group_client_id": [f"G{i:04d}" for i in range(1, N_CLIENTS + 1)],
                        "client_name": [f"Sponsor {i:03d}" for i in range(1, N_CLIENTS + 1)]})
clients["hq_region"] = rng.choice(REGIONS, N_CLIENTS, p=REGION_W)
clients["size_segment"] = rng.choice(["Small biotech", "Mid-size biopharma", "Large pharma"], N_CLIENTS, p=[0.55, 0.35, 0.10])
clients["uses_cro"] = rng.random(N_CLIENTS) < 0.50
clients["uses_pv"] = rng.random(N_CLIENTS) < 0.62
clients["uses_adamas"] = rng.random(N_CLIENTS) < 0.38
clients["weight"] = clients.size_segment.map({"Small biotech": 1.0, "Mid-size biopharma": 2.2, "Large pharma": 4.0})
clients["cro_code"] = [f"ECR-A{1000 + i * 7}" if u else "" for i, u in enumerate(clients.uses_cro)]
clients["pv_code"] = [f"PV{70000 + i * 13}" if u else "" for i, u in enumerate(clients.uses_pv)]


def pick_client(flag):
    pool = clients[clients[flag]]
    return pool.sample(1, weights=pool.weight, random_state=int(rng.integers(1e9))).iloc[0]


def country_for(region):
    return rng.choice(COUNTRIES[region])


def creation_dates(per_year, growth=0.08):
    days = bdays(START, END)
    t = (days - START).days / 365
    lam = per_year / 252 * (1 + growth) ** t
    n = rng.poisson(lam)
    return [d for d, k in zip(days, n) for _ in range(k)]


# ------------------------------------------------------------------ CRO (EUR, CRM export)
CRO_TA = (["Oncology", "Rare disease", "CNS", "Immunology", "Other"], [0.48, 0.32, 0.08, 0.07, 0.05])
CRO_PHASE = (["Phase I", "Phase II", "Phase III", "Phase IV"], [0.18, 0.40, 0.32, 0.10])
CRO_VALUE = {"Phase I": (12.85, 0.35), "Phase II": (13.63, 0.35), "Phase III": (14.40, 0.35), "Phase IV": (13.26, 0.35)}
DROP_FROM = pd.Timestamp("2026-03-01")      # planted issue 7: Europe oncology bid-defense win rate falls


def cro_records(drop=True):
    rows = []
    for i, created in enumerate(creation_dates(380)):
        c = pick_client("uses_cro")
        region = c.hq_region if rng.random() < 0.8 else rng.choice(REGIONS, p=REGION_W)
        ta = ch(CRO_TA)
        phase = ch(CRO_PHASE)
        mu, sd = CRO_VALUE[phase]
        value = round(float(rng.lognormal(mu, sd)), -3)
        r = dict(opp_id=f"CRO-{10001 + i}", account_code=c.cro_code, account_name=c.client_name, group_client_id=c.group_client_id,
                 region=region, country=country_for(region), ta=ta, phase=phase, services="Clinical", value_eur=value,
                 created=created, rfp=None, proposal=None, bid_defense=None, award=None, contract=None, lost=None,
                 cancelled=None, loss_reason="", stage=None)
        if rng.random() < 0.10:                                     # no bid / disqualified
            r["lost"], r["loss_reason"] = add(created, 10, 30), "No bid"
        else:
            r["rfp"] = add(created, 0, 10)
            r["proposal"] = add(r["rfp"], 20, 35)
            if rng.random() < 0.70:
                r["bid_defense"] = add(r["proposal"], 25, 50)
                decision = qend_pull(add(r["bid_defense"], 10, 35), 0.5)
                p_win = 0.47
                if drop and region == "Europe" and ta == "Oncology" and decision >= DROP_FROM:
                    p_win = 0.10
                if rng.random() < p_win:
                    r["award"] = decision
                    if rng.random() < 0.08:                         # verbal award never contracted (issue 2)
                        r["lost"], r["loss_reason"] = add(decision, 30, 70), "Award not contracted"
                    else:
                        r["contract"] = add(decision, 25, 60) if rng.random() > 0.05 else add(decision, 95, 150)
                        if rng.random() < 0.03:
                            r["cancelled"] = add(r["contract"], 60, 240)
                else:
                    r["lost"], r["loss_reason"] = decision, rng.choice(["Price", "Competitor capability", "Timeline", "Sponsor cancelled programme"])
            else:
                r["lost"], r["loss_reason"] = add(r["proposal"], 30, 60), rng.choice(["Price", "Not shortlisted"])
        rows.append(r)
    return rows


# ------------------------------------------------------------------ PV (USD, recurring contracts)
PV_TA = (["Oncology", "Rare disease", "CNS", "Cardiometabolic", "Immunology", "Infectious disease", "Other"],
         [0.24, 0.20, 0.15, 0.14, 0.11, 0.10, 0.06])
PV_SERVICE = ["Full PV outsourcing", "Case processing", "QPPV & PSMF", "Literature surveillance", "Signal management",
              "Medical information"]


def pv_records():
    rows = []
    for i, created in enumerate(creation_dates(430)):
        c = pick_client("uses_pv")
        region = c.hq_region if rng.random() < 0.85 else rng.choice(REGIONS, p=REGION_W)
        acv = round(float(rng.lognormal(12.55, 0.45)), -3)
        years = int(rng.choice([1, 2, 3, 3, 4, 5]))
        r = dict(deal_ref=f"PVD-{24001 + i}", client_ref=c.pv_code, client=c.client_name, group_client_id=c.group_client_id,
                 region=region, country=country_for(region), product_area=ch(PV_TA),
                 service=rng.choice(PV_SERVICE, p=[0.25, 0.25, 0.15, 0.12, 0.12, 0.11]), acv=acv, years=years,
                 created=created, qualified=None, proposal=None, negotiation=None, signed=None, lost=None, origin="")
        if rng.random() < 0.20:
            r["lost"] = add(created, 5, 25)
        else:
            r["qualified"] = add(created, 5, 20)
            if rng.random() < 0.15:
                r["lost"] = add(r["qualified"], 10, 40)
            else:
                r["proposal"] = add(r["qualified"], 15, 40)
                if rng.random() < 0.30:
                    r["lost"] = add(r["proposal"], 20, 50)
                else:
                    r["negotiation"] = add(r["proposal"], 15, 40)
                    d = qend_pull(add(r["negotiation"], 10, 30), 0.5)
                    if rng.random() < 0.66:
                        r["signed"] = d
                    else:
                        r["lost"] = d
        rows.append(r)
    return rows


# ------------------------------------------------------------------ ADAMAS (GBP, audits)
AUDIT_TYPES = (["GCP audit", "GVP audit", "GMP audit", "GLP audit", "Computer systems validation", "Mock inspection"],
               [0.36, 0.22, 0.16, 0.08, 0.10, 0.08])


def adamas_records():
    rows = []
    for i, created in enumerate(creation_dates(560, 0.05)):
        c = pick_client("uses_adamas")
        region = c.hq_region if rng.random() < 0.85 else rng.choice(REGIONS, p=REGION_W)
        quote = round(float(rng.lognormal(10.2, 0.5)), -2)
        r = dict(ref=f"ADM-{5001 + i}", client=c.client_name, group_client_id=c.group_client_id, region=region,
                 audit_type=ch(AUDIT_TYPES), requested=created, quote_sent=None, quote_gbp=quote, status="Enquiry",
                 confirmed=None, declined=None, audit_date=None)
        if rng.random() < 0.08:
            r["status"], r["declined"] = "Withdrawn", add(created, 3, 15)
        else:
            r["quote_sent"] = add(created, 2, 10)
            d = qend_pull(add(r["quote_sent"], 5, 25), 0.3)
            if rng.random() < 0.66:
                r["status"], r["confirmed"] = "Confirmed", d
                r["audit_date"] = add(d, 20, 75)
            else:
                r["status"], r["declined"] = "Declined", d
        rows.append(r)
    return rows


def state_at(r, cut, steps):
    """Return the record as it looked at `cut`: dates after the cut are blanked."""
    out = dict(r)
    for s in steps:
        if out.get(s) is not None and pd.Timestamp(out[s]) > cut:
            out[s] = None
    return out


def expected_won(reps=24):
    """Targets are set on the *expected* new business of each business x region (what a plan would assume), not on
    one random draw: the generators are re-run `reps` times with their own seeds and without the planted drop."""
    global rng
    saved, out = rng, []
    for k in range(reps):
        rng = np.random.default_rng(1000 + k)
        for r in cro_records(drop=False):
            if r["contract"] is not None:
                out.append(("Ergomed CRO", r["region"], r["contract"].year, r["value_eur"] * fx(r["contract"], "EUR")))
        for r in pv_records():
            if r["signed"] is not None:
                out.append(("PrimeVigilance", r["region"], r["signed"].year, r["acv"] * r["years"]))
        for r in adamas_records():
            if r["confirmed"] is not None:
                reg = r["region"] if r["region"] != "Rest of World" else "Europe"     # tracker cannot separate RoW
                out.append(("ADAMAS", reg, r["confirmed"].year, r["quote_gbp"] * fx(r["confirmed"], "GBP")))
    rng = saved
    e = pd.DataFrame(out, columns=["business", "region", "year", "usd"])
    return e.groupby(["business", "region", "year"]).usd.sum() / reps


# ------------------------------------------------------------------ build
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    truth = []
    cro, pv, adm = cro_records(), pv_records(), adamas_records()
    cro_steps = ["rfp", "proposal", "bid_defense", "award", "contract", "lost", "cancelled"]
    cro = [state_at(r, END, cro_steps) for r in cro if r["created"] <= END]
    pv_steps = ["qualified", "proposal", "negotiation", "signed", "lost"]
    pv_full = [state_at(r, END, pv_steps) for r in pv if r["created"] <= END]
    adm = [state_at(r, END, ["quote_sent", "confirmed", "declined", "audit_date"]) for r in adm if r["requested"] <= END]

    # --- issue 1: integrated CRO + PV deals booked in both systems (PV scope inside the CRO amount AND in PV)
    won_cro = [r for r in cro if r["contract"] is not None and r["contract"] >= pd.Timestamp("2025-01-01")
               and clients.set_index("group_client_id").loc[r["group_client_id"], "uses_pv"]]
    picks = rng.choice(len(won_cro), 7, replace=False)
    for k, idx in enumerate(picks):
        r = won_cro[idx]
        r["services"] = "Clinical + PV"
        tcv = round(float(rng.uniform(0.6e6, 1.8e6)), -3)
        years = 3
        r["value_eur"] = round(r["value_eur"] + tcv / fx(r["contract"], "EUR"), -3)
        c = clients.set_index("group_client_id").loc[r["group_client_id"]]
        d = add(r["contract"], -10, 20)
        pv_full.append(dict(deal_ref=f"PVD-{29001 + k}", client_ref=c.pv_code, client=c.client_name,
                            group_client_id=r["group_client_id"], region=r["region"], country=r["country"],
                            product_area=r["ta"], service="Full PV outsourcing", acv=round(tcv / years, -3), years=years,
                            created=add(r["created"], 20, 60), qualified=None, proposal=None, negotiation=None,
                            signed=min(d, END), lost=None,
                            origin=f"Cross-sell ({r['opp_id']})" if k % 2 == 0 else "Ergomed CRO referral"))
        truth.append(dict(issue=1, name="Cross-sell deal counted twice", source="cro_crm + pv_pipeline",
                          record=f"{r['opp_id']} / PVD-{29001 + k}", true_value_usd=round(tcv),
                          note="PV scope included in the CRO amount and booked again in PV; count it once, in PV"))

    # --- issue 4: one large CRO win entered twice
    big = max((r for r in cro if r["contract"] is not None and pd.Timestamp("2026-01-01") <= r["contract"] < pd.Timestamp("2026-10-01")),
              key=lambda r: r["value_eur"])
    dup = dict(big)
    dup["opp_id"] = f"CRO-{10001 + len(cro) + 3}"
    dup["created"] = big["contract"] - pd.Timedelta(days=2)
    dup["_name_variant"] = True
    cro.append(dup)
    truth.append(dict(issue=4, name="Large win entered twice in the CRM", source="cro_crm", record=f"{big['opp_id']} / {dup['opp_id']}",
                      true_value_usd=round(big["value_eur"] * fx(big["contract"], "EUR")),
                      note="same account, amount, phase and dates; second record created at contract signature"))

    # ---------------- write CRO CRM (xlsx)
    def stage(r):
        if r["cancelled"] is not None:
            return "Cancelled"
        if r["lost"] is not None:
            return "Closed Lost" if r["loss_reason"] != "No bid" else "No Bid"
        for s, name in (("contract", "Contracted"), ("award", "Awarded"), ("bid_defense", "Bid Defense"),
                        ("proposal", "Proposal Submitted"), ("rfp", "RFP Received")):
            if r[s] is not None:
                return name
        return "Qualification"
    prob = {"Qualification": 5, "RFP Received": 10, "Proposal Submitted": 25, "Bid Defense": 50, "Awarded": 90,
            "Contracted": 100, "Closed Lost": 0, "No Bid": 0, "Cancelled": 0}
    crm = []
    for r in cro:
        s = stage(r)
        name = f"{r['phase'].replace('Phase ', 'Ph ')} {r['ta']} study"
        if r.get("_name_variant"):
            name = f"{r['phase']} {r['ta'].lower()} trial"
        last = max(d for d in [r["created"], r["rfp"], r["proposal"], r["bid_defense"], r["award"], r["contract"],
                               r["lost"], r["cancelled"]] if d is not None)
        crm.append({"Opportunity ID": r["opp_id"], "Account Code": r["account_code"], "Account Name": r["account_name"],
                    "Opportunity Name": name, "Region": CRO_REGION_CODE[r["region"]], "Country": r["country"],
                    "Therapeutic Area": r["ta"], "Phase": r["phase"], "Services": r["services"], "Stage": s,
                    "Amount (EUR)": r["value_eur"], "Probability (%)": prob[s], "Created Date": r["created"],
                    "RFP Received": r["rfp"], "Proposal Submitted": r["proposal"], "Bid Defense Date": r["bid_defense"],
                    "Award Date": r["award"], "Contract Signed": r["contract"], "Closed Lost Date": r["lost"],
                    "Cancellation Date": r["cancelled"], "Loss Reason": r["loss_reason"], "Last Modified": last})
    crm = pd.DataFrame(crm).sort_values("Created Date")
    with pd.ExcelWriter(OUT / "cro_crm.xlsx", engine="openpyxl") as xw:
        crm.to_excel(xw, sheet_name="Opportunities", index=False)
        pd.DataFrame({"Export": ["CRM opportunity export", "Generated 2026-11-09 07:30", "Currency: EUR",
                                 "Filter: all opportunities created since 2024-03-01"]}).to_excel(xw, sheet_name="Export info", index=False)

    # ---------------- write PV pipeline (csv) and the late North America file (issue 5)
    def pv_status(r):
        if r["signed"] is not None:
            return "Signed"
        if r["lost"] is not None:
            return "Closed Lost"
        for s, name in (("negotiation", "Negotiation"), ("proposal", "Proposal Sent"), ("qualified", "Qualified")):
            if r[s] is not None:
                return name
        return "Lead"

    def pv_frame(records, ts):
        out = []
        for r in records:
            changed = max(d for d in [r["created"], r["qualified"], r["proposal"], r["negotiation"], r["signed"], r["lost"]] if d is not None)
            out.append({"deal_ref": r["deal_ref"], "client_ref": r["client_ref"], "client": r["client"], "country": r["country"],
                        "product_area": r["product_area"], "service": r["service"], "pipeline_status": pv_status(r),
                        "annual_value_usd": r["acv"], "contract_years": r["years"], "tcv_usd": r["acv"] * r["years"],
                        "created_on": r["created"].date(), "proposal_sent_on": r["proposal"].date() if r["proposal"] is not None else "",
                        "signed_on": r["signed"].date() if r["signed"] is not None else "", "status_changed_on": changed.date(),
                        "origin": r["origin"], "tracker": f"PV BD {r['region'] if r['region'] in ('Europe', 'North America') else 'APAC & RoW'}",
                        "extract_ts": ts})
        return pd.DataFrame(out).sort_values("created_on")

    week_start = pd.Timestamp("2026-11-02")
    na_cut = week_start - pd.Timedelta(days=1)
    nego = [r for r in pv_full if r["region"] == "North America" and r["negotiation"] is not None
            and r["negotiation"] <= na_cut and r["signed"] is None and r["lost"] is None]
    for r in nego[:3]:
        r["signed"] = bdays(week_start, week_start + pd.Timedelta(days=4))[int(rng.integers(5))]       # NA tracker in the on-time file is last week's version
    on_time = [state_at(r, na_cut, pv_steps) if r["region"] == "North America" else r for r in pv_full
               if not (r["region"] == "North America" and r["created"] > na_cut)]
    pv_frame(on_time, "2026-11-09 08:55").to_csv(OUT / "pv_pipeline.csv", index=False)
    late = [r for r in pv_full if r["region"] == "North America"]
    pv_frame(late, "2026-11-11 15:20").to_csv(OUT / "pv_pipeline_na_late.csv", index=False)
    late_signed = [r for r in late if r["signed"] is not None and r["signed"] >= week_start]
    truth.append(dict(issue=5, name="Late data owner (PV North America, week 45)", source="pv_pipeline",
                      record=";".join(r["deal_ref"] for r in late_signed),
                      true_value_usd=round(sum(r["acv"] * r["years"] for r in late_signed)),
                      note="NA tracker received Wed 11 Nov 15:20, deadline Mon 9 Nov 10:00; on-time file holds last week's NA state"))

    # ---------------- write ADAMAS tracker (xlsx, manual, merged cells, mixed formats)
    wb = Workbook()
    ws = wb.active
    ws.title = "Audit tracker"
    ws["A1"] = "ADAMAS - AUDIT ENQUIRIES & BOOKINGS (working file - do not sort)"
    ws["A1"].font = Font(bold=True, size=13)
    ws.merge_cells("A1:J1")
    ws["A2"] = "Values in GBP unless stated. Status: Enquiry / Quoted / Confirmed / Declined / Withdrawn"
    ws.merge_cells("A2:J2")
    header = ["Ref", "Client", "Audit type", "Region", "Requested", "Quote sent", "Quote (GBP)", "Status", "Confirmed on", "Comments"]
    ws.append([])
    ws.append(header)
    for cell in ws[4]:
        cell.font = Font(bold=True)
    df = pd.DataFrame(adm).sort_values("requested")
    df["month"] = df.requested.dt.to_period("M")
    row = 5
    status_variants = {"Confirmed": ["Confirmed"] * 8 + ["confirmed ", "CONF"], "Declined": ["Declined", "declined"],
                       "Withdrawn": ["Withdrawn"], "Enquiry": ["Enquiry", "Quoted"]}
    for m, g in df.groupby("month"):
        ws.cell(row=row, column=1, value=m.strftime("%B %Y").upper()).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="52514E")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
        row += 1
        for client, gc in g.groupby("client", sort=False):
            first = row
            for r in gc.itertuples():
                status = rng.choice(status_variants[r.status])
                if r.status == "Enquiry" and pd.notna(r.quote_sent):
                    status = "Quoted"
                quote = r.quote_gbp if rng.random() > 0.15 else f"£{r.quote_gbp:,.0f}"
                when = r.confirmed if pd.notna(r.confirmed) else None
                req = r.requested.to_pydatetime() if rng.random() > 0.06 else r.requested.strftime("%d/%m/%Y")
                ws.append([r.ref, client if row == first else None, r.audit_type, ADAMAS_REGION[r.region] if r.region != "Europe" or rng.random() > 0.3 else "UK",
                           req, r.quote_sent.to_pydatetime() if pd.notna(r.quote_sent) else None, quote, status,
                           when.to_pydatetime() if when is not None else ("TBC" if r.status == "Confirmed" else None),
                           f"audit planned {r.audit_date:%d %b}" if pd.notna(r.audit_date) else ""])
                row += 1
            if row - first > 1:
                ws.merge_cells(start_row=first, start_column=2, end_row=row - 1, end_column=2)
                ws.cell(row=first, column=2).alignment = Alignment(vertical="center")
    for col, w in zip("ABCDEFGHIJ", [10, 16, 26, 11, 12, 12, 12, 11, 13, 24]):
        ws.column_dimensions[col].width = w
    wb.properties.creator = ""
    wb.properties.lastModifiedBy = ""
    wb.save(OUT / "adamas_tracker.xlsx")

    # ---------------- clients master (ADAMAS has no code: matched on name)
    cm = clients[["group_client_id", "client_name", "hq_region", "size_segment", "cro_code", "pv_code"]].copy()
    cm.columns = ["group_client_id", "client_name", "hq_region", "size_segment", "cro_account_code", "pv_client_ref"]
    drop = cm.sample(4, random_state=7).index                    # 4 clients missing from the master (DQ check)
    cm.drop(drop).to_csv(OUT / "clients_master.csv", index=False)

    # ---------------- revenue actuals (finance, USD) and targets
    months = pd.period_range("2024-11", "2026-10", freq="M")
    base = {"Ergomed CRO": 8.6e6, "PrimeVigilance": 11.4e6, "ADAMAS": 1.25e6}
    rev = []
    for b, m0 in base.items():
        for i, m in enumerate(months):
            tot = m0 * (1.006 ** i) * (0.93 if m.month == 8 else 1.0) * rng.normal(1, 0.035)
            shares = REGION_W * rng.normal(1, 0.04, 4)
            for reg, s in zip(REGIONS, shares / shares.sum()):
                rev.append(dict(business=b, region=reg, month=str(m), revenue_usd=round(tot * s, -2)))
    pd.DataFrame(rev).to_csv(OUT / "revenue_actuals.csv", index=False)
    # finance: contracted order book at 31 Oct 2024 (opening balance for the order-book roll-forward), USD
    pd.DataFrame([dict(business="Ergomed CRO", order_book_usd=232.0e6), dict(business="PrimeVigilance", order_book_usd=171.0e6),
                  dict(business="ADAMAS", order_book_usd=5.2e6)]).assign(as_of="2024-10-31").to_csv(OUT / "order_book_opening.csv", index=False)

    # targets "as received": annual target per business x region, split annual / 12 (planted issue 6)
    exp = expected_won()
    targets = {}
    for year, stretch in ((2025, 1.00), (2026, 1.00)):
        e = exp.xs(year, level="year")
        targets[year] = (e * stretch * rng.normal(1, 0.02, len(e))).round(-4)
    with pd.ExcelWriter(OUT / "targets.xlsx", engine="openpyxl") as xw:
        for year, t in targets.items():
            sheet = pd.DataFrame([{"Business": b, "Region": r, "FY target (USD)": v,
                                   **{pd.Timestamp(year, m, 1).strftime("%b-%y"): round(v / 12, -2) for m in range(1, 13)}}
                                  for (b, r), v in t.items()])
            sheet.to_excel(xw, sheet_name=f"FY{year}", index=False)
    truth.append(dict(issue=6, name="Target phased flat (annual / 12) on a seasonal business", source="targets.xlsx",
                      record="all sheets", true_value_usd=None,
                      note="won value peaks in the last month of each quarter; flat phasing makes Q1/Q2 months look behind"))

    # ---------------- source log (weekly submissions, issue 5)
    log = []
    owners = [("cro_crm.xlsx", "CRO Sales Operations", "Global"), ("pv_pipeline.csv", "PV BD Europe", "Europe"),
              ("pv_pipeline.csv", "PV BD North America", "North America"), ("pv_pipeline.csv", "PV BD APAC & RoW", "Asia-Pacific; Rest of World"),
              ("adamas_tracker.xlsx", "ADAMAS Operations", "Global")]
    for wk in pd.date_range("2024-11-04", "2026-11-09", freq="W-MON"):
        deadline = wk + pd.Timedelta(hours=10)
        for src, owner, scope in owners:
            delay = rng.normal(-14, 5)
            if rng.random() < 0.03:
                delay = rng.uniform(1, 6)                                  # occasional, minor
            if wk == pd.Timestamp("2026-11-09") and owner == "PV BD North America":
                received = pd.Timestamp("2026-11-11 15:20")
            else:
                received = deadline + pd.Timedelta(hours=float(delay))
            log.append(dict(week_ending=(wk - pd.Timedelta(days=1)).date(), source_file=src, data_owner=owner, scope=scope,
                            deadline=deadline, received=received.round("min"), on_time=received <= deadline))
    pd.DataFrame(log).to_csv(OUT / "source_log.csv", index=False)

    # ---------------- remaining answer-key rows
    truth += [
        dict(issue=2, name="Stage names do not match across businesses", source="all", record="stage columns",
             true_value_usd=None, note="CRO 'Awarded' is a verbal award (8% never contracted); PV 'Signed' and ADAMAS 'Confirmed' are contracts"),
        dict(issue=3, name="Currencies summed as if equal", source="all", record="value columns",
             true_value_usd=None, note="CRO EUR, PV USD, ADAMAS GBP; convert at the ECB monthly average of the win month"),
        dict(issue=7, name="Europe behind target: oncology bid-defense win rate", source="cro_crm",
             record="Region EU, TA Oncology, decisions from 2026-03-01", true_value_usd=None,
             note="win probability at bid defense falls from 0.47 to 0.10; volume and deal size unchanged"),
        dict(issue=8, name="False signal: quarter-end spike in wins", source="all", record="last week of Mar/Jun/Sep/Dec",
             true_value_usd=None, note="decisions due within 45 days of quarter end pulled to its last week, p=0.5 (CRO, PV) / 0.3 (ADAMAS), every quarter"),
    ]
    pd.DataFrame(truth).sort_values("issue").to_csv(ROOT / "data" / "_hidden_truth.csv", index=False)
    print(f"CRO {len(crm)} | PV {len(on_time)} (+{len(late)} NA late) | ADAMAS {len(adm)} | clients {len(cm) - 4} in master")


if __name__ == "__main__":
    main()
