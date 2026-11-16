"""PUBLIC DATA - ClinicalTrials.gov extract -> clean study table and market aggregates.

Scope: interventional, industry lead sponsor, start date 2019-2025 (src/collect_trials.py).
Therapeutic flags: oncology = MeSH Neoplasms (D009369) among the registry's condition terms or ancestors;
rare disease = PROXY (MeSH 'Genetic Diseases, Inborn' D030342 in the ancestors, or 'rare'/'orphan' in conditions or
keywords), see src/collect_trials.py.
Sponsor size proxy: number of studies the lead sponsor started in the window (1-5 small, 6-50 mid, 51+ large).
This is a proxy for 'how big a trial portfolio', not revenue or headcount; stated as such wherever used.
Countries: a study counts once per country where it has at least one site.
Outputs: data/public/ct_studies.csv, ct_by_year.csv, ct_by_country.csv, ct_by_phase_size.csv, ct_ergomed.csv
No person names are read or kept (no investigator / contact / official fields are requested).
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "clinicaltrials"
PUB = ROOT / "data" / "public"
PHASE = {"EARLY_PHASE1": "Phase I", "PHASE1": "Phase I", "PHASE2": "Phase II", "PHASE3": "Phase III", "PHASE4": "Phase IV",
         "NA": "Not applicable"}
EUROPE = {"United Kingdom", "Germany", "France", "Spain", "Italy", "Netherlands", "Belgium", "Poland", "Czechia", "Hungary",
          "Austria", "Switzerland", "Sweden", "Denmark", "Norway", "Finland", "Ireland", "Portugal", "Greece", "Romania",
          "Bulgaria", "Croatia", "Serbia", "Slovakia", "Slovenia", "Lithuania", "Latvia", "Estonia", "Ukraine", "Georgia",
          "Russian Federation", "Belarus", "Moldova, Republic of", "Bosnia and Herzegovina", "North Macedonia", "Iceland",
          "Luxembourg", "Cyprus", "Malta", "Albania", "Montenegro"}
NA_ = {"United States", "Canada"}
APAC = {"China", "Japan", "Korea, Republic of", "Australia", "Taiwan", "India", "Singapore", "Hong Kong", "New Zealand",
        "Thailand", "Malaysia", "Philippines", "Vietnam", "Indonesia"}


def region(c):
    return "Europe" if c in EUROPE else "North America" if c in NA_ else "Asia-Pacific" if c in APAC else "Rest of World"


def load(pattern):
    f = sorted(RAW.glob(pattern))[-1]
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        s = json.loads(line)["protocolSection"]
        idm, sp, de, st = s.get("identificationModule", {}), s.get("sponsorCollaboratorsModule", {}), s.get("designModule", {}), s.get("statusModule", {})
        cb = json.loads(line).get("derivedSection", {}).get("conditionBrowseModule", {})
        mesh = {m.get("id") for m in cb.get("meshes", []) + cb.get("ancestors", [])}
        cm = s.get("conditionsModule", {})
        words = " ".join(cm.get("conditions", []) + cm.get("keywords", [])).lower()
        locs = s.get("contactsLocationsModule", {}).get("locations", [])
        phases = de.get("phases", []) or ["NA"]
        rows.append(dict(nct_id=idm.get("nctId"), lead_sponsor=sp.get("leadSponsor", {}).get("name"),
                         collaborators="; ".join(c.get("name", "") for c in sp.get("collaborators", [])),
                         phase=PHASE.get(phases[-1], "Not applicable"), start=st.get("startDateStruct", {}).get("date"),
                         status=st.get("overallStatus"), oncology="D009369" in mesh, rare=("D030342" in mesh) or ("rare" in words.split()) or ("orphan" in words),
                         countries="; ".join(sorted({l.get("country") for l in locs if l.get("country")})),
                         enrollment=de.get("enrollmentInfo", {}).get("count")))
    return pd.DataFrame(rows), f.name


def main():
    if not list(RAW.glob("studies_*.jsonl")):
        print("raw ClinicalTrials.gov extract not present (run src/collect_trials.py): keeping data/public/ct_*.csv as is")
        return
    df, fname = load("studies_*.jsonl")
    df["start_year"] = pd.to_datetime(df.start, errors="coerce").dt.year
    df = df[df.start_year.between(2019, 2025)].copy()
    n_by_sponsor = df.groupby("lead_sponsor").nct_id.transform("count")
    df["sponsor_size"] = pd.cut(n_by_sponsor, [0, 5, 50, 1e9], labels=["Small (1-5 studies)", "Mid (6-50)", "Large (51+)"]).astype(str)
    df["area"] = df.apply(lambda r: "Oncology + rare" if r.oncology and r.rare else "Oncology" if r.oncology
                          else "Rare disease" if r.rare else "Other areas", axis=1)
    df["focus"] = df.oncology | df.rare
    # some industry sponsors / collaborators are registered under a person's name: names are not published,
    # only an anonymous sponsor id and the size class (aggregates do not need them)
    pub = df.drop(columns=["collaborators"]).copy()
    pub["lead_sponsor"] = [f"S{i:05d}" for i in pd.factorize(pub.lead_sponsor)[0]]
    pub.rename(columns={"lead_sponsor": "sponsor_id"}).to_csv(PUB / "ct_studies.csv", index=False)

    by_year = df.groupby(["start_year", "area"]).size().unstack(fill_value=0)
    by_year.to_csv(PUB / "ct_by_year.csv")
    f = df[df.focus]
    ps = f.groupby(["phase", "sponsor_size"]).size().unstack(fill_value=0)
    ps.to_csv(PUB / "ct_by_phase_size.csv")
    ex = f.assign(country=f.countries.str.split("; ")).explode("country")
    ex = ex[ex.country.notna() & (ex.country != "")]
    by_c = ex.groupby("country").agg(studies=("nct_id", "nunique"),
                                     small_mid_share=("sponsor_size", lambda s: (s != "Large (51+)").mean())).sort_values("studies", ascending=False)
    by_c["region"] = [region(c) for c in by_c.index]
    by_c.to_csv(PUB / "ct_by_country.csv")
    reg = ex.groupby(ex.country.map(region)).nct_id.nunique()

    erg, _ = load("ergomed_*.jsonl")
    erg = erg[(erg.lead_sponsor.str.contains("Ergomed|PrimeVigilance", case=False, na=False))
              | (erg.collaborators.str.contains("Ergomed|PrimeVigilance", case=False, na=False))]
    erg["role"] = erg.lead_sponsor.str.contains("Ergomed|PrimeVigilance", case=False).map({True: "Lead sponsor", False: "Collaborator"})
    erg[["nct_id", "role", "phase", "start", "status", "oncology", "rare"]].to_csv(PUB / "ct_ergomed.csv", index=False)

    summary = dict(source_file=fname, collected="2026-11-16", studies=int(len(df)), focus_studies=int(f.shape[0]),
                   focus_share=round(float(df.focus.mean()), 3),
                   small_mid_share_focus=round(float((f.sponsor_size != "Large (51+)").mean()), 3),
                   small_mid_share_other=round(float((df[~df.focus].sponsor_size != "Large (51+)").mean()), 3),
                   phase2_3_share_focus=round(float(f.phase.isin(["Phase II", "Phase III"]).mean()), 3),
                   focus_by_region={k: int(v) for k, v in reg.items()},
                   top_countries={k: int(v) for k, v in by_c.studies.head(8).items()},
                   ergomed_studies=int(len(erg)), ergomed_roles=erg.role.value_counts().to_dict(),
                   focus_2019=int(by_year.loc[2019].drop("Other areas").sum()), focus_2025=int(by_year.loc[2025].drop("Other areas").sum()))
    (PUB / "ct_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
