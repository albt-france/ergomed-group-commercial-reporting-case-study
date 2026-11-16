"""Collect the public sources used in the case study (dated snapshots, low request rate).

1. Companies House (UK register, free): annual reports / accounts filed by
   - Ergomed Group Limited (04081094), formerly Ergomed plc (AIM-listed until November 2023)
   - Eden TopCo Limited (15049295), the parent that consolidates the group since the take-private (FY2024 on)
   - Ergomed Clinical Research Limited (05094681), the UK trading entity
   PDFs come from the public "View PDF" links. If COMPANIES_HOUSE_API_KEY is set in .env the official API is not
   needed for this script; it is kept optional.
2. ClinicalTrials.gov API v2 (public domain): see src/collect_trials.py.
3. Group websites (services, locations): see WEB_PAGES below, robots.txt checked, one request every few seconds.

Output: data/raw/... (not redistributed, see .gitignore). Run again to download the same files.
"""
import time
import urllib.robotparser
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_CH = ROOT / "data" / "raw" / "companies_house"
RAW_WEB = ROOT / "data" / "raw" / "web"
CH_SITE = "https://find-and-update.company-information.service.gov.uk"
HEADERS = {"User-Agent": "Mozilla/5.0 (independent case study; low-rate research)"}
PAUSE_S = 3
TODAY = date.today().isoformat()

# (file name, company number, transaction id) - from the public filing history, read on 2026-11-16
FILINGS = [
    ("EGL_group_accounts_FY2019.pdf", "04081094", "MzI2NzMyNTY5N2FkaXF6a2N4"),
    ("EGL_group_accounts_FY2020.pdf", "04081094", "MzMwNTE2NjMyM2FkaXF6a2N4"),
    ("EGL_group_accounts_FY2021.pdf", "04081094", "MzM0MjYxMDM1MmFkaXF6a2N4"),
    ("EGL_group_accounts_FY2022.pdf", "04081094", "MzM4NDQ0NDk2MmFkaXF6a2N4"),
    ("EGL_group_accounts_FY2023.pdf", "04081094", "MzQzNzk1OTIyNmFkaXF6a2N4"),
    ("EGL_accounts_FY2024.pdf", "04081094", "MzQ4MzQ3MzkwMGFkaXF6a2N4"),
    ("EGL_accounts_FY2025.pdf", "04081094", "MzU0OTA1MTY1MWFkaXF6a2N4"),
    ("EdenTopCo_group_accounts_FY2024.pdf", "15049295", "MzQ3MDc0NTczN2FkaXF6a2N4"),
    ("EdenTopCo_group_accounts_FY2025.pdf", "15049295", "MzUyNDY3ODk1N2FkaXF6a2N4"),
    ("ECR_accounts_FY2022.pdf", "05094681", "MzM5MzgwNTE1OGFkaXF6a2N4"),
    ("ECR_accounts_FY2023.pdf", "05094681", "MzQzNzk1OTIyOGFkaXF6a2N4"),
    ("ECR_accounts_FY2024.pdf", "05094681", "MzQ4MzQ3MzkwMWFkaXF6a2N4"),
    ("ECR_accounts_FY2025.pdf", "05094681", "MzU0OTA1MTY1NGFkaXF6a2N4"),
]

WEB_PAGES = {
    "ergomedgroup_home": "https://ergomedgroup.com/",
    "ergomedgroup_about": "https://ergomedgroup.com/about-us/",
    "primevigilance_home": "https://primevigilance.com/",
    "adamas_home": "https://www.adamasconsulting.com/",
}


def allowed(url: str) -> bool:
    rp = urllib.robotparser.RobotFileParser()
    base = "/".join(url.split("/")[:3])
    try:
        rp.set_url(base + "/robots.txt")
        rp.read()
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True


def download_accounts():
    RAW_CH.mkdir(parents=True, exist_ok=True)
    for name, company, tid in FILINGS:
        target = RAW_CH / name
        if target.exists():
            continue
        url = f"{CH_SITE}/company/{company}/filing-history/{tid}/document"
        r = requests.get(url, params={"format": "pdf", "download": 0}, headers=HEADERS, timeout=120)
        r.raise_for_status()
        target.write_bytes(r.content)
        print("saved", name, len(r.content) // 1024, "KB")
        time.sleep(PAUSE_S)


def download_web_pages():
    RAW_WEB.mkdir(parents=True, exist_ok=True)
    for name, url in WEB_PAGES.items():
        if not allowed(url):
            print("robots.txt disallows", url)
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            print(name, r.status_code)
            if r.ok:
                (RAW_WEB / f"{name}_{TODAY}.html").write_text(r.text, encoding="utf-8")
        except requests.RequestException as e:
            print(name, "failed:", e)
        time.sleep(PAUSE_S)


if __name__ == "__main__":
    download_accounts()
    download_web_pages()
