"""Competitor benchmarks (PUBLIC DATA): annual reports filed with the SEC (EDGAR) by three listed CROs.
Backlog, net new business awards and book-to-bill are not XBRL-tagged, so the script downloads the annual report
(10-K or 20-F) main document and extracts the sentences that state them; src/extract_competitors.py then keeps the
figures with the filing and sentence they come from. Generic User-Agent, one request every 2 s (SEC fair-access policy:
max 10 requests/s)."""
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "competitors"
H = {"User-Agent": "IndependentCaseStudy research-bot"}
COMPANIES = {"IQVIA": "0001478242", "ICON": "0001060955", "Medpace": "0001668397"}
FORMS = {"10-K", "20-F"}
YEARS = range(2021, 2027)


def get(url):
    time.sleep(2)
    r = requests.get(url, headers=H, timeout=60)
    r.raise_for_status()
    return r


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name, cik in COMPANIES.items():
        sub = get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
        rec = sub["filings"]["recent"]
        for form, date, acc, doc in zip(rec["form"], rec["filingDate"], rec["accessionNumber"], rec["primaryDocument"]):
            if form in FORMS and int(date[:4]) in YEARS:
                target = RAW / f"{name}_{form}_{date}.htm"
                if not target.exists():
                    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
                    target.write_text(get(url).text, encoding="utf-8")
                    (RAW / f"{target.stem}.url").write_text(url)
                    print("saved", target.name)


if __name__ == "__main__":
    main()
