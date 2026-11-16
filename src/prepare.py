"""Governed preparation: three raw exports -> one commercial model (data/processed/), with automatic quality checks.

Why Python and not only Power Query: the per-source shaping (rename, type, map stages/regions, convert currency) is
also written in M (powerquery/*.pq) so the business can refresh it in Power BI. Four steps are done here because they
are cross-source or fuzzy and must be logged for review: duplicate detection, cross-sell double counting between CRO
and PV, the late-file substitution, and the reconciliation report. Each is a named function below.

Inputs  data/simulated/*  (SIMULATED), data/public/fx_rates_ecb.csv (PUBLIC DATA), docs/governance/mappings/*.csv
Outputs data/processed/
  fact_opportunity.csv  one row per opportunity, harmonised (common stage, USD, group client id, region)
  fact_target.csv       targets by business x region x month: as received (flat) and re-phased (seasonal)
  fact_revenue.csv      recognised revenue (finance) + order-book opening balance
  dim_*.csv             date, business, region, therapeutic area, client, stage, stage map
  dq_issues.csv         one row per check x source x data owner (rows flagged, severity, status, action)
  data_health.csv       freshness / completeness per source and owner (latest week)
  reconciliation.csv    source totals vs model totals, row counts, value by currency
  naive_vs_governed.csv the 'just stack the files' answer vs the governed answer (bridge)
  sec_user_scope.csv    RLS mapping user -> business x region (fictional @example.com accounts)
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SIM, PUB, MAP = ROOT / "data" / "simulated", ROOT / "data" / "public", ROOT / "docs" / "governance" / "mappings"
OUT = ROOT / "data" / "processed"
AS_OF = pd.Timestamp("2026-11-11 16:00")          # model refresh time (after the late PV North America file)
CUT = pd.Timestamp("2026-11-08")                   # data up to the end of week 45
BUSINESSES = ["Ergomed CRO", "PrimeVigilance", "ADAMAS"]
REGIONS = ["Europe", "North America", "Asia-Pacific", "Rest of World"]
OWNER = {"Ergomed CRO": "CRO Sales Operations", "ADAMAS": "ADAMAS Operations"}

FX = pd.read_csv(PUB / "fx_rates_ecb.csv").pivot(index="month", columns="currency", values="rate_to_usd")
STAGES = pd.read_csv(MAP / "stage_map.csv")
COUNTRY_REGION = pd.read_csv(MAP / "country_region_map.csv").set_index("country").region
REGION_MAP = pd.read_csv(MAP / "region_map.csv")
DQ = []


def dq(check_id, check, source, owner, rows, severity, status, action):
    DQ.append(dict(check_id=check_id, check=check, source=source, data_owner=owner, rows_flagged=int(rows),
                   severity=severity, status=status, action=action))


def rate(d, ccy):
    """ECB monthly average of the month of `d`; months not yet published use the last published month."""
    m = pd.Series(pd.to_datetime(d)).dt.strftime("%Y-%m").fillna(FX.index.max()).clip(upper=FX.index.max())
    return m.map(FX[ccy]).values, (m.values == FX.index.max()) & (pd.Series(pd.to_datetime(d)).dt.strftime("%Y-%m") > FX.index.max()).values


# ------------------------------------------------------------------ CRO
def load_cro():
    raw = pd.read_excel(SIM / "cro_crm.xlsx", sheet_name="Opportunities")
    df = pd.DataFrame({
        "source_id": raw["Opportunity ID"], "client_code": raw["Account Code"], "client_name": raw["Account Name"],
        "region_src": raw["Region"], "country": raw["Country"], "therapeutic_area": raw["Therapeutic Area"],
        "detail": raw["Phase"], "services": raw["Services"], "source_stage": raw["Stage"], "currency": "EUR",
        "value_local": raw["Amount (EUR)"], "probability": raw["Probability (%)"] / 100,
        "created_date": raw["Created Date"], "proposal_date": raw["Proposal Submitted"], "award_date": raw["Award Date"],
        "won_date": raw["Contract Signed"], "lost_date": raw["Closed Lost Date"], "cancel_date": raw["Cancellation Date"],
        "loss_reason": raw["Loss Reason"].fillna(""), "opp_name": raw["Opportunity Name"]})
    df["business"] = "Ergomed CRO"
    rm = REGION_MAP[REGION_MAP.business == "Ergomed CRO"].set_index("source_value").region
    df["region"] = df.region_src.map(rm)
    df["data_owner"] = OWNER["Ergomed CRO"]
    return raw, df


def dedupe_cro(df):
    """Planted issue 4: the same win keyed twice. Same account, amount, phase, therapeutic area and contract date:
    keep the record created first, exclude the other (logged)."""
    key = ["client_code", "value_local", "detail", "therapeutic_area", "won_date"]
    won = df[df.won_date.notna()].sort_values("created_date")
    dup = won[won.duplicated(key, keep="first")]
    dq("DQ01", "Duplicate opportunity (same account, amount, phase, area, contract date)", "cro_crm.xlsx",
       OWNER["Ergomed CRO"], len(dup), "ERROR", "Resolved in model",
       "Second record excluded; CRM owner asked to merge " + ", ".join(dup.source_id))
    return df[~df.source_id.isin(dup.source_id)].copy(), dup


# ------------------------------------------------------------------ PV
def load_pv():
    on_time = pd.read_csv(SIM / "pv_pipeline.csv")
    late = pd.read_csv(SIM / "pv_pipeline_na_late.csv")
    log = pd.read_csv(SIM / "source_log.csv", parse_dates=["deadline", "received"])
    na = log[(log.data_owner == "PV BD North America")].sort_values("deadline").iloc[-1]
    raw = on_time
    if na.received <= AS_OF:     # late file received before this refresh: it replaces the NA tracker rows
        raw = pd.concat([on_time[on_time.tracker != "PV BD North America"], late], ignore_index=True)
    df = pd.DataFrame({
        "source_id": raw.deal_ref, "client_code": raw.client_ref, "client_name": raw.client, "country": raw.country,
        "therapeutic_area": raw.product_area, "detail": raw.service, "source_stage": raw.pipeline_status,
        "currency": "USD", "value_local": raw.tcv_usd, "acv_usd": raw.annual_value_usd, "contract_years": raw.contract_years,
        "created_date": pd.to_datetime(raw.created_on), "proposal_date": pd.to_datetime(raw.proposal_sent_on),
        "won_date": pd.to_datetime(raw.signed_on), "status_changed": pd.to_datetime(raw.status_changed_on),
        "origin": raw.origin.fillna(""), "data_owner": raw.tracker})
    df["lost_date"] = np.where(df.source_stage == "Closed Lost", df.status_changed, pd.NaT)
    df["lost_date"] = pd.to_datetime(df.lost_date)
    df["business"] = "PrimeVigilance"
    df["region"] = df.country.map(COUNTRY_REGION)
    df["probability"] = df.source_stage.map({"Lead": .05, "Qualified": .15, "Proposal Sent": .35, "Negotiation": .65,
                                             "Signed": 1.0, "Closed Lost": 0.0})
    return on_time, late, df


# ------------------------------------------------------------------ ADAMAS (manual tracker)
STATUS_STD = {"confirmed": "Confirmed", "conf": "Confirmed", "declined": "Declined", "withdrawn": "Withdrawn",
              "enquiry": "Enquiry", "quoted": "Quoted"}


def parse_date(v):
    if v is None or (isinstance(v, str) and v.strip().upper() in ("", "TBC")):
        return pd.NaT, isinstance(v, str)
    if isinstance(v, str):
        return pd.to_datetime(v, dayfirst=True), True
    return pd.Timestamp(v), False


def load_adamas():
    wb = load_workbook(SIM / "adamas_tracker.xlsx")
    ws = wb["Audit tracker"]
    merged = [str(r) for r in ws.merged_cells.ranges]
    rows, client = [], None
    text_dates = text_quotes = tbc = 0
    status_raw = []
    for r in ws.iter_rows(min_row=5, values_only=True):
        ref = r[0]
        if not ref or not str(ref).startswith("ADM-"):
            continue                                   # month banner rows (merged across the sheet)
        client = r[1] or client                        # merged client cells: value only on the first row
        req, t1 = parse_date(r[4])
        qs, _ = parse_date(r[5])
        conf, t2 = parse_date(r[8])
        q = r[6]
        if isinstance(q, str):
            text_quotes += 1
            q = float(re.sub(r"[^\d.]", "", q))
        st = STATUS_STD[str(r[7]).strip().lower()]
        status_raw.append(str(r[7]))
        tbc += int(isinstance(r[8], str) and r[8].strip().upper() == "TBC")
        text_dates += int(t1)
        rows.append(dict(source_id=ref, client_name=client, detail=r[2], region_src=r[3], created_date=req,
                         proposal_date=qs, source_stage=st, value_local=q, won_date=conf if st == "Confirmed" else pd.NaT,
                         confirmed_tbc=st == "Confirmed" and pd.isna(conf)))
    df = pd.DataFrame(rows)
    # a confirmed booking with 'TBC' as date: use the quote date + 14 days as provisional win date (flagged)
    df.loc[df.confirmed_tbc, "won_date"] = df.loc[df.confirmed_tbc, "proposal_date"] + pd.Timedelta(days=14)
    df["lost_date"] = pd.NaT                     # the tracker has no decline date: provisional = quote date + 14 days
    lost = df.source_stage.isin(["Declined", "Withdrawn"])
    df.loc[lost, "lost_date"] = df.loc[lost, "proposal_date"].fillna(df.loc[lost, "created_date"]) + pd.Timedelta(days=14)
    df["business"], df["currency"], df["therapeutic_area"] = "ADAMAS", "GBP", "Not applicable (audit)"
    rm = REGION_MAP[REGION_MAP.business == "ADAMAS"].set_index("source_value").region
    df["region"] = df.region_src.map(rm)
    df["country"] = ""
    df["data_owner"] = OWNER["ADAMAS"]
    df["probability"] = df.source_stage.map({"Enquiry": .1, "Quoted": .6, "Confirmed": 1, "Declined": 0, "Withdrawn": 0})
    n_variants = sum(s not in ("Confirmed", "Declined", "Withdrawn", "Enquiry", "Quoted") for s in status_raw)
    o = OWNER["ADAMAS"]
    dq("DQ06", "Non-standard status spelling ('CONF', 'confirmed ', ...)", "adamas_tracker.xlsx", o, n_variants, "WARNING",
       "Resolved in model", "Mapped to the standard list; data-validation drop-down proposed for the tracker")
    dq("DQ07", "Confirmed booking without a confirmation date ('TBC')", "adamas_tracker.xlsx", o, tbc, "WARNING", "Open",
       "Provisional date = quote date + 14 days; owner to enter the real date")
    dq("DQ08", "Dates typed as text (dd/mm/yyyy)", "adamas_tracker.xlsx", o, text_dates, "INFO", "Resolved in model", "Parsed day-first")
    dq("DQ09", "Quote stored as text with a currency sign", "adamas_tracker.xlsx", o, text_quotes, "INFO", "Resolved in model",
       "Converted to number")
    dq("DQ14", "Merged cells (client name on the first row only, month banners)", "adamas_tracker.xlsx", o, len(merged), "INFO",
       "Resolved in model", "Forward-filled; move the tracker to a list (one row per audit, no merges)")
    return df


# ------------------------------------------------------------------ cross-source steps
def map_clients(df, master):
    by_cro = master.dropna(subset=["cro_account_code"]).set_index("cro_account_code").group_client_id
    by_pv = master.dropna(subset=["pv_client_ref"]).set_index("pv_client_ref").group_client_id
    by_name = master.set_index(master.client_name.str.lower().str.strip()).group_client_id
    gid = pd.Series(index=df.index, dtype=object)
    m = df.business == "Ergomed CRO"
    gid[m] = df.loc[m, "client_code"].map(by_cro)
    m = df.business == "PrimeVigilance"
    gid[m] = df.loc[m, "client_code"].map(by_pv)
    m = df.business == "ADAMAS"
    gid[m] = df.loc[m, "client_name"].str.lower().str.strip().map(by_name)
    # fall back on the (anonymous) name for codes missing from the master
    miss = gid.isna()
    gid[miss] = df.loc[miss, "client_name"].str.lower().str.strip().map(by_name)
    still = gid.isna()
    for b, g in df[still].groupby("business"):
        dq("DQ10", "Client not in the client master (matched on name or left unmapped)", source_of(b),
           "Commercial Operations (master data)", g.client_name.nunique(), "WARNING", "Open",
           "Add to clients_master.csv: " + ", ".join(sorted(g.client_name.unique())[:6]))
    gid[still] = "UNMAPPED:" + df.loc[still, "client_name"]
    df["group_client_id"] = gid
    return df


def source_of(b):
    return {"Ergomed CRO": "cro_crm.xlsx", "PrimeVigilance": "pv_pipeline.csv", "ADAMAS": "adamas_tracker.xlsx"}[b]


def cross_sell(df):
    """Planted issue 1: an integrated CRO + PV deal booked in full in the CRM ('Clinical + PV') and the PV scope
    booked again as a PV contract. Match: same group client, CRO 'Clinical + PV' won, PV deal signed within 45 days.
    Match priority: the PV 'origin' field names the CRO opportunity > it says 'CRO referral' > nearest date.
    Rule: the PV scope is counted once, in PV; the CRO amount is reduced by the PV contract value."""
    cro = df[(df.business == "Ergomed CRO") & (df.services == "Clinical + PV") & df.won_date.notna()]
    pv = df[(df.business == "PrimeVigilance") & df.won_date.notna()]
    pairs = []
    for i, c in cro.iterrows():
        cand = pv[(pv.group_client_id == c.group_client_id) & ((pv.won_date - c.won_date).abs().dt.days <= 45)].copy()
        if len(cand):
            # priority: PV deal that names the CRO opportunity > PV deal marked as a CRO referral > nearest signature date
            origin = cand.origin.fillna("").str.lower()
            cand["prio"] = [0 if c.source_id.lower() in o else 1 if ("cro" in o or "cross-sell" in o) else 2 for o in origin]
            cand["gap"] = (cand.won_date - c.won_date).abs().dt.days
            j = cand.sort_values(["prio", "gap"]).index[0]
            pairs.append((i, j))
    df["cross_sell_adj_usd"] = 0.0
    df["cross_sell_with"] = ""
    df["is_cross_sell"] = False
    for i, j in pairs:
        df.loc[i, "cross_sell_adj_usd"] = -df.loc[j, "value_usd"]
        df.loc[[i, j], "is_cross_sell"] = True
        df.loc[j, "cross_sell_with"] = df.loc[i, "source_id"]
        df.loc[i, "cross_sell_with"] = df.loc[j, "source_id"]
    dq("DQ02", "Cross-sell deal counted in CRO and in PV", "cro_crm.xlsx + pv_pipeline.csv", "CRO Sales Operations; PV BD",
       len(pairs), "ERROR", "Resolved in model", "PV scope deducted from the CRO amount; rule added to the KPI dictionary")
    return df, pairs


def common_stage(df):
    sm = STAGES.set_index(["business", "source_stage"])
    k = list(zip(df.business, df.source_stage))
    df["common_stage"] = [sm.loc[x, "common_stage"] for x in k]
    df["status"] = [sm.loc[x, "status"] for x in k]
    pv_early = (df.business == "PrimeVigilance") & (df.status == "Lost") & df.proposal_date.isna()
    df.loc[pv_early, ["common_stage", "status"]] = ["6 Disqualified", "Disqualified"]
    unmapped = df.common_stage.isna().sum()
    dq("DQ04", "Source stage without a mapping to the common stages", "all", "Commercial Operations", unmapped,
       "ERROR" if unmapped else "INFO", "OK" if not unmapped else "Open", "docs/governance/mappings/stage_map.csv")
    return df


# ------------------------------------------------------------------ main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(SIM / "clients_master.csv")
    cro_raw, cro = load_cro()
    cro, dups = dedupe_cro(cro)
    pv_on_time, pv_late, pv = load_pv()
    adm = load_adamas()
    df = pd.concat([cro, pv, adm], ignore_index=True)
    df = map_clients(df, master)
    df = common_stage(df)

    # currency: won deals at the ECB monthly average of the win month; open/lost at the month of the last event
    ref_date = df.won_date.fillna(df.lost_date).fillna(CUT)
    df["fx_rate"] = 1.0
    df["fx_provisional"] = False
    for ccy in ("EUR", "GBP"):
        m = df.currency == ccy
        r, prov = rate(ref_date[m], ccy)
        df.loc[m, "fx_rate"] = r
        df.loc[m, "fx_provisional"] = prov
    df["value_usd"] = (df.value_local * df.fx_rate).round(0)
    dq("DQ03", "Values in EUR / GBP converted to USD at the ECB monthly average", "cro_crm.xlsx; adamas_tracker.xlsx",
       "Commercial Operations", (df.currency != "USD").sum(), "INFO", "OK", "Rule in KPI_DICTIONARY.md (FX policy)")
    dq("DQ03b", "November 2026 rate not yet published: last published month used", "all", "Commercial Operations",
       df.fx_provisional.sum(), "WARNING", "Open", "Re-run after the ECB publishes the monthly average")

    df["services"] = df.services.fillna("")
    df, pairs = cross_sell(df)
    df["value_usd_governed"] = df.value_usd + df.cross_sell_adj_usd
    df["acv_usd"] = df.acv_usd.fillna(np.nan)
    df["weighted_value_usd"] = (df.value_usd_governed * df.probability).round(0)
    df["decision_date"] = df.won_date.where(df.status == "Won", df.lost_date)
    df.loc[df.status == "Open", "decision_date"] = pd.NaT
    df["reached_proposal"] = df.proposal_date.notna() | df.status.eq("Won")
    df["in_win_rate"] = df.status.isin(["Won", "Lost"]) & df.reached_proposal
    df["cycle_days"] = (df.decision_date - df.created_date).dt.days.where(df.status == "Won")
    df["verbal_award_open"] = (df.business == "Ergomed CRO") & (df.source_stage == "Awarded")
    stale = df.verbal_award_open & ((CUT - df.award_date).dt.days > 90)
    dq("DQ11", "Verbal award older than 90 days without a signed contract", "cro_crm.xlsx", OWNER["Ergomed CRO"],
       stale.sum(), "WARNING", "Open", "Confirm with the business development lead: contract pending or lost?")
    open_old = (df.status == "Open") & (df.business == "PrimeVigilance") & ((CUT - df.get("status_changed")).dt.days > 120)
    for owner, g in df[open_old].groupby("data_owner"):
        dq("DQ12", "Open PV deal without a status change for 120+ days", "pv_pipeline.csv", owner, len(g), "WARNING", "Open",
           "Owner to update or close")

    df["opp_key"] = np.arange(1, len(df) + 1)
    df["detail"] = df.detail.fillna("")
    cols = ["opp_key", "business", "source_id", "group_client_id", "client_name", "region", "country", "therapeutic_area",
            "detail", "services", "source_stage", "common_stage", "status", "currency", "value_local", "fx_rate",
            "fx_provisional", "value_usd", "cross_sell_adj_usd", "value_usd_governed", "acv_usd", "probability",
            "weighted_value_usd", "created_date", "proposal_date", "award_date", "won_date", "lost_date", "decision_date",
            "cancel_date", "reached_proposal", "in_win_rate", "cycle_days", "is_cross_sell", "verbal_award_open",
            "loss_reason", "data_owner", "cross_sell_with"]
    fact = df[cols].copy()
    for c in ("created_date", "proposal_date", "award_date", "won_date", "lost_date", "decision_date", "cancel_date"):
        fact[c] = pd.to_datetime(fact[c]).dt.date
    fact.to_csv(OUT / "fact_opportunity.csv", index=False)

    # ---------------- targets: as received (flat) and re-phased on last year's monthly shape (issue 6)
    t = []
    for sheet, year in (("FY2025", 2025), ("FY2026", 2026)):
        x = pd.read_excel(SIM / "targets.xlsx", sheet_name=sheet)
        for _, r in x.iterrows():
            for m in range(1, 13):
                t.append(dict(business=r.Business, region=r.Region, month=pd.Timestamp(year, m, 1).date(),
                              target_flat_usd=r[pd.Timestamp(year, m, 1).strftime("%b-%y")], fy_target_usd=r["FY target (USD)"]))
    t = pd.DataFrame(t)
    won = fact[fact.status == "Won"].copy()
    won["m"] = pd.to_datetime(won.won_date).dt.month
    won["y"] = pd.to_datetime(won.won_date).dt.year
    # month-in-quarter profile (M1 / M2 / M3) of FY2025 won value per business, applied to equal quarters:
    # robust to one lumpy month, and it is the pattern the business actually has (quarter-end signatures)
    won["miq"] = (won.m - 1) % 3 + 1
    prof = (won[won.y == 2025].groupby(["business", "miq"]).value_usd_governed.sum()
            / won[won.y == 2025].groupby("business").value_usd_governed.sum()).rename("share").reset_index()
    prof["share"] = prof.share / 4
    t["m"] = pd.to_datetime(t.month).dt.month
    t["miq"] = (t.m - 1) % 3 + 1
    t = t.merge(prof, on=["business", "miq"], how="left")
    t["target_phased_usd"] = np.where(pd.to_datetime(t.month).dt.year == 2026, (t.fy_target_usd * t.share).round(-2), t.target_flat_usd)
    t[["business", "region", "month", "target_flat_usd", "target_phased_usd", "fy_target_usd"]].to_csv(OUT / "fact_target.csv", index=False)
    dq("DQ13", "Targets phased flat (annual / 12) on a seasonal business", "targets.xlsx", "FP&A", len(t) // 12, "WARNING", "Open",
       "Phased target proposed (FY2025 month-in-quarter profile per business); FP&A to approve")

    rev = pd.read_csv(SIM / "revenue_actuals.csv")
    rev["month"] = pd.to_datetime(rev.month + "-01").dt.date
    rev.to_csv(OUT / "fact_revenue.csv", index=False)
    pd.read_csv(SIM / "order_book_opening.csv").to_csv(OUT / "order_book_opening.csv", index=False)

    # ---------------- dimensions
    d = pd.DataFrame({"date": pd.date_range("2024-01-01", "2026-12-31")})
    d["year"], d["month_num"] = d.date.dt.year, d.date.dt.month
    d["month"] = d.date.dt.to_period("M").dt.to_timestamp().dt.date
    d["month_label"] = d.date.dt.strftime("%b %y")
    d["quarter"] = "Q" + d.date.dt.quarter.astype(str) + " " + d.year.astype(str)
    d["week_ending"] = (d.date + pd.to_timedelta(6 - d.date.dt.day_of_week, unit="D")).dt.date
    qe = d.date + pd.offsets.QuarterEnd(0)
    d["quarter_end_week"] = (qe - d.date).dt.days < 7
    d["is_closed_month"] = d.date < pd.Timestamp("2026-11-01")
    d["date"] = d.date.dt.date
    d.to_csv(OUT / "dim_date.csv", index=False)
    pd.DataFrame({"business": BUSINESSES, "business_sort": [1, 2, 3], "source_currency": ["EUR", "USD", "GBP"],
                  "value_basis": ["Contract value (EUR), signed contract", "Total contract value = annual value x years (USD)",
                                  "Confirmed audit quote (GBP)"],
                  "won_definition": ["Contracted (not 'Awarded')", "Signed", "Confirmed"]}).to_csv(OUT / "dim_business.csv", index=False)
    pd.DataFrame({"region": REGIONS, "region_sort": [1, 2, 3, 4]}).to_csv(OUT / "dim_region.csv", index=False)
    tas = sorted(fact.therapeutic_area.unique())
    pd.DataFrame({"therapeutic_area": tas, "ta_group": ["Oncology & rare disease" if t in ("Oncology", "Rare disease")
                                                        else ("Audit" if "audit" in t else "Other areas") for t in tas]}).to_csv(OUT / "dim_therapeutic_area.csv", index=False)
    cl = master.copy()
    extra = fact[fact.group_client_id.str.startswith("UNMAPPED")][["group_client_id", "client_name"]].drop_duplicates()
    cl = pd.concat([cl, extra.assign(hq_region="Unknown", size_segment="Unknown")], ignore_index=True)
    nb = fact[fact.status == "Won"].groupby("group_client_id").business.nunique()
    cl["businesses_won"] = cl.group_client_id.map(nb).fillna(0).astype(int)
    cl["multi_business_client"] = cl.businesses_won >= 2
    cl[["group_client_id", "client_name", "hq_region", "size_segment", "businesses_won", "multi_business_client"]].to_csv(OUT / "dim_client.csv", index=False)
    st = STAGES[["common_stage", "stage_order"]].drop_duplicates().sort_values("stage_order")
    st.to_csv(OUT / "dim_stage.csv", index=False)
    STAGES.to_csv(OUT / "stage_map.csv", index=False)

    # ---------------- data health (latest week) and DQ table
    log = pd.read_csv(SIM / "source_log.csv", parse_dates=["deadline", "received"])
    log["hours_late"] = ((log.received - log.deadline).dt.total_seconds() / 3600).clip(lower=0).round(1)
    last = log[log.week_ending == log.week_ending.max()].copy()
    rows_by_owner = fact.groupby("data_owner").size()
    last["rows_in_model"] = last.data_owner.map(lambda o: int(rows_by_owner.get(o, 0)))
    last["on_time_rate_52w"] = last.data_owner.map(log[log.week_ending > str(pd.Timestamp(log.week_ending.max()) - pd.Timedelta(weeks=52))]
                                                   .groupby("data_owner").on_time.mean().round(3))
    req = {"cro_crm.xlsx": ["client_name", "region", "therapeutic_area", "value_local", "created_date"],
           "pv_pipeline.csv": ["client_name", "region", "therapeutic_area", "value_local", "created_date"],
           "adamas_tracker.xlsx": ["client_name", "region", "value_local", "created_date"]}
    comp = {}
    for b in BUSINESSES:
        sub = df[df.business == b]
        cols_req = req[source_of(b)]
        comp[source_of(b)] = float(sub[cols_req].notna().all(axis=1).mean().round(4))
    last["completeness"] = last.source_file.map(comp)
    last["status"] = np.where(last.on_time, "On time", "LATE")
    last["impact"] = ""
    na_late = last.data_owner.eq("PV BD North America") & ~last.on_time
    if na_late.any():
        new_signed = pv_late[pd.to_datetime(pv_late.signed_on) >= "2026-11-02"]
        last.loc[na_late, "impact"] = (f"{len(new_signed)} signed deals (${new_signed.tcv_usd.sum() / 1e6:.1f}m TCV) "
                                       "missing from the Monday report; restated after receipt")
        dq("DQ05", "Source received after the reporting deadline (week 45)", "pv_pipeline.csv", "PV BD North America",
           len(new_signed), "ERROR", "Open", "Weekly report flagged INCOMPLETE; restated Wed 11 Nov; escalation per REPORTING_CALENDAR.md")
    last.to_csv(OUT / "data_health.csv", index=False)
    log.to_csv(OUT / "source_log.csv", index=False)

    # ---------------- reconciliation: source -> model
    rec = []
    def add(source, check, src_val, model_val, note):
        rec.append(dict(source=source, check=check, source_value=src_val, model_value=model_val,
                        difference=round(model_val - src_val, 2), status="OK" if abs(model_val - src_val) < 0.5 else "Explained", note=note))
    add("cro_crm.xlsx", "Rows", len(cro_raw), (fact.business == "Ergomed CRO").sum(), f"{len(dups)} duplicate excluded")
    add("cro_crm.xlsx", "Amount, EUR (all records)", cro_raw["Amount (EUR)"].sum(),
        fact.loc[fact.business == "Ergomed CRO", "value_local"].sum(), "duplicate excluded")
    pv_src = pd.concat([pv_on_time[pv_on_time.tracker != "PV BD North America"], pv_late])
    add("pv_pipeline.csv (+ NA late file)", "Rows", len(pv_src), (fact.business == "PrimeVigilance").sum(), "late NA file replaces the NA rows")
    add("pv_pipeline.csv (+ NA late file)", "TCV, USD", pv_src.tcv_usd.sum(), fact.loc[fact.business == "PrimeVigilance", "value_local"].sum(), "")
    add("adamas_tracker.xlsx", "Audit rows (excl. banners)", len(adm), (fact.business == "ADAMAS").sum(), "month banner rows dropped")
    add("All", "Won value USD: before vs after cross-sell rule", fact.loc[fact.status == "Won", "value_usd"].sum(),
        fact.loc[fact.status == "Won", "value_usd_governed"].sum(), f"{len(pairs)} cross-sell pairs: PV scope counted once")
    rev_src = pd.read_csv(SIM / "revenue_actuals.csv").revenue_usd.sum()
    add("revenue_actuals.csv", "Revenue USD", rev_src, rev.revenue_usd.sum(), "finance file loaded as is")
    pd.DataFrame(rec).to_csv(OUT / "reconciliation.csv", index=False)

    # ---------------- naive vs governed (Jan-Oct 2026)
    ytd = (pd.to_datetime(df.won_date.fillna(df.award_date)) >= "2026-01-01") & (pd.to_datetime(df.won_date.fillna(df.award_date)) < "2026-11-01")
    naive_won = df.source_stage.isin(["Awarded", "Contracted", "Cancelled", "Signed", "Confirmed"])
    dup_rows = dups[(pd.to_datetime(dups.won_date) >= "2026-01-01") & (pd.to_datetime(dups.won_date) < "2026-11-01")]
    gov = fact[(fact.status == "Won") & (pd.to_datetime(fact.won_date) >= "2026-01-01") & (pd.to_datetime(fact.won_date) < "2026-11-01")]
    naive_local = df.loc[ytd & naive_won, "value_local"].sum() + dup_rows.value_local.sum()
    dup_usd = (dup_rows.value_local * rate(dup_rows.won_date, "EUR")[0]).sum()
    step_fx = df.loc[ytd & naive_won, "value_usd"].sum() + dup_usd - naive_local
    step_dup = -dup_usd
    after_dup = naive_local + step_fx + step_dup
    governed_before_xs = gov.value_usd.sum()
    step_stage = governed_before_xs - after_dup
    step_xs = gov.value_usd_governed.sum() - governed_before_xs
    bridge = pd.DataFrame([
        ("Naive: stack the three files", naive_local, "sum of value columns, EUR + USD + GBP, 'Awarded' counted as won, duplicate included"),
        ("Convert EUR and GBP to USD", step_fx, "ECB monthly average of the win month"),
        ("Remove the duplicate CRM record", step_dup, "planted issue 4"),
        ("Won = signed contract, not verbal award", step_stage, "CRO 'Awarded' -> open; won dated at signature"),
        ("Count cross-sell PV scope once", step_xs, "planted issue 1"),
        ("Governed: new business won, Jan-Oct 2026", gov.value_usd_governed.sum(), "model value"),
    ], columns=["step", "value", "note"])
    bridge["value"] = bridge.value.round(0)
    bridge.to_csv(OUT / "naive_vs_governed.csv", index=False)

    # naive vs governed win rate
    naive_wr = naive_won[df.created_date >= "2025-01-01"].mean()
    gov_wr = fact[(pd.to_datetime(fact.decision_date) >= "2025-01-01") & fact.in_win_rate].status.eq("Won").mean()

    # ---------------- RLS mapping (fictional accounts)
    users = [("exec.team@example.com", "All", "All"), ("cro.lead@example.com", "Ergomed CRO", "All"),
             ("pv.lead@example.com", "PrimeVigilance", "All"), ("adamas.lead@example.com", "ADAMAS", "All"),
             ("europe.lead@example.com", "All", "Europe"), ("na.lead@example.com", "All", "North America"),
             ("pv.na.manager@example.com", "PrimeVigilance", "North America")]
    sec = [dict(user_principal_name=u, business=b2, region=r2) for u, b, r in users
           for b2 in (BUSINESSES if b == "All" else [b]) for r2 in (REGIONS if r == "All" else [r])]
    pd.DataFrame(sec).to_csv(OUT / "sec_user_scope.csv", index=False)

    dqdf = pd.DataFrame(DQ)
    dqdf.to_csv(OUT / "dq_issues.csv", index=False)
    summary = dict(as_of=str(AS_OF), rows=int(len(fact)), won_ytd_usd=float(gov.value_usd_governed.sum()),
                   naive_ytd=float(naive_local), cross_sell_pairs=len(pairs), duplicates=len(dups),
                   naive_win_rate=round(float(naive_wr), 3), governed_win_rate=round(float(gov_wr), 3),
                   dq_open=int((dqdf.status == "Open").sum()), dq_checks=int(dqdf.check_id.nunique()))
    (OUT / "prep_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
