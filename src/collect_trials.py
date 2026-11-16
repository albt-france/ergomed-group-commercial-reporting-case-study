"""ClinicalTrials.gov API v2 (PUBLIC DATA, U.S. National Library of Medicine, public domain).

Scope: interventional studies with an INDUSTRY lead sponsor and a start date from 2019-01-01 to 2025-12-31.
Only organisation-level fields are kept: no investigator, contact or official names are requested.
Therapeutic flags use the registry's own MeSH indexing of the conditions (ConditionBrowseModule: meshes + ancestors):
oncology = Neoplasms (D009369) in the terms or their ancestors. The API (checked 2026-11-16) no longer returns the
'Rare Diseases' browse branch, so rare disease is a documented PROXY: MeSH 'Genetic Diseases, Inborn' (D030342) in the
ancestors, or 'rare' / 'orphan' in the conditions or keywords. It misses rare diseases that are not inborn and not
labelled as rare by the sponsor, and is reported as a proxy.

Output: data/raw/clinicaltrials/studies_<date>.jsonl (raw, not redistributed) and
        data/public/ct_studies.csv (one row per study, cleaned; built by src/prepare_public.py).
A second query lists the studies where an Ergomed entity is lead sponsor or collaborator.
"""
import json
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "clinicaltrials"
API = "https://clinicaltrials.gov/api/v2/studies"
H = {"User-Agent": "IndependentCaseStudy research-bot"}
FIELDS = ",".join([
    "NCTId", "LeadSponsorName", "LeadSponsorClass", "CollaboratorName", "CollaboratorClass", "Phase", "StartDate",
    "OverallStatus", "LocationCountry", "ConditionBrowseModule", "Condition", "Keyword", "EnrollmentCount", "StudyType",
])
ADVANCED = "AREA[StudyType]INTERVENTIONAL AND AREA[LeadSponsorClass]INDUSTRY AND AREA[StartDate]RANGE[2019-01-01,2025-12-31]"


def fetch(params, target):
    n, token = 0, None
    with open(target, "w", encoding="utf-8") as fh:
        while True:
            p = dict(params, pageSize=1000, fields=FIELDS, format="json")
            if token:
                p["pageToken"] = token
            for attempt in range(4):
                try:
                    r = requests.get(API, params=p, headers=H, timeout=90)
                    r.raise_for_status()
                    break
                except requests.RequestException:
                    time.sleep(5 * (attempt + 1))
            else:
                raise RuntimeError("ClinicalTrials.gov API unavailable")
            j = r.json()
            for s in j.get("studies", []):
                fh.write(json.dumps(s) + "\n")
                n += 1
            token = j.get("nextPageToken")
            if not token:
                break
            time.sleep(1.0)
    print(target.name, n, "studies")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    fetch({"filter.advanced": ADVANCED}, RAW / f"studies_{today}.jsonl")
    fetch({"query.spons": "Ergomed OR PrimeVigilance"}, RAW / f"ergomed_{today}.jsonl")


if __name__ == "__main__":
    main()
