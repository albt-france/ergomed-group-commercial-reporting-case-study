"""PUBLIC DATA - commercial KPIs of three listed CROs, as published (no judgement, dated and sourced).

Medpace and IQVIA: figures typed from the 10-K filings downloaded by src/collect_competitors.py; when the raw files
are present, the script re-reads each 10-K and stops if a typed figure cannot be found in it (source check).
ICON: backlog and wins are published in the quarterly results releases (Form 6-K), not in the 20-F; typed from the
releases cited below. ICON changed its backlog and cancellation methodology on 1 Oct 2025 (backlog -USD 3.9bn).

Definitions differ between companies (this is the point of the comparison):
  Medpace  net new business awards / total revenue (our computation from the 10-K figures)
  IQVIA    R&D Solutions segment only; awards not in the 10-K -> implied = change in backlog + segment revenue
           (ignores FX and cancellations; labelled 'implied')
  ICON     net business wins / revenue, as published by the company
Output: data/public/competitors.csv
"""
import html
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "competitors"
OUT = ROOT / "data" / "public" / "competitors.csv"
EDGAR = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={}&type=10-K"

MEDPACE = {  # year: (backlog USDm, net new business awards USDm, revenue USDm)
    2020: (1541.7, 1175.0, 925.9), 2021: (1997.1, 1610.4, 1142.4), 2022: (2339.6, 1829.5, 1460.0),
    2023: (2813.0, 2356.7, 1885.8), 2024: (2902.2, 2230.0, 2109.1), 2025: (3027.2, 2646.8, 2530.2)}
IQVIA = {  # year: (R&DS contracted backlog USDbn, R&DS revenue USDm)
    2019: (19.0, 5788), 2020: (22.6, 5760), 2021: (24.8, 7556), 2022: (27.2, 7921), 2023: (29.7, 8395),
    2024: (31.1, 8527), 2025: (32.7, 8896)}
ICON = {  # year: (backlog USDbn, net wins USDm, gross wins USDm, cancellations USDm, revenue USDm, book-to-bill, source)
    2024: (24.7, 9974, 12082, 2108, 8282, 1.20,
           "ICON Q4 & FY2024 results release, 19 Feb 2025 (Form 6-K): sec.gov/Archives/edgar/data/1060955/000106095525000013/q42024pressrelease.htm"),
    2025: (21.8, 9033, 11867, 2834, 8251.3, 1.09,
           "ICON Q4 & FY2025 results release, 27 May 2026: iconplc.com/news-events/press-releases/icon-reports-fourth-quarter-and-full-year-2025-results "
           "(backlog under the methodology effective 1 Oct 2025)"),
}


def raw_text(prefix):
    out = {}
    for f in RAW.glob(f"{prefix}_10-K_*.htm"):
        t = re.sub(r"<[^>]+>", " ", f.read_text(encoding="utf-8", errors="ignore"))
        out[f.name] = re.sub(r"\s+", " ", html.unescape(t)).replace("$ ", "$")
    return " ".join(out.values())


def source_check():
    med, iq = raw_text("Medpace"), raw_text("IQVIA")
    if not med or not iq:
        print("raw 10-K files not present: source check skipped")
        return
    for y, (b, a, _) in MEDPACE.items():
        assert f"${b:,.1f} million" in med, f"Medpace backlog {y}"
        assert f"${a:,.1f} million" in med, f"Medpace awards {y}"
    for y, (b, r) in IQVIA.items():
        assert f"${b:.1f} billion" in iq, f"IQVIA backlog {y}"
        assert f"${r:,}" in iq, f"IQVIA revenue {y}"
    print("source check: every typed Medpace / IQVIA figure found in the 10-K text")


def main():
    source_check()
    rows = []
    for y, (b, a, r) in MEDPACE.items():
        rows.append(dict(company="Medpace", year=y, backlog_usd_bn=round(b / 1000, 2), net_awards_usd_m=a, revenue_usd_m=r,
                         book_to_bill=round(a / r, 2), btb_basis="net new business awards / revenue (computed)",
                         cancellation_rate=None, source=f"Medpace Holdings 10-K for FY{y} (SEC EDGAR, CIK 1668397); revenue from XBRL"))
    for y, (b, r) in IQVIA.items():
        prev = IQVIA.get(y - 1)
        implied = round((b - prev[0]) * 1000 + r) if prev else None
        rows.append(dict(company="IQVIA (R&D Solutions)", year=y, backlog_usd_bn=b, net_awards_usd_m=implied, revenue_usd_m=r,
                         book_to_bill=round(implied / r, 2) if implied else None,
                         btb_basis="implied: change in backlog + segment revenue", cancellation_rate=None,
                         source=f"IQVIA Holdings 10-K for FY{y} (SEC EDGAR, CIK 1478242), R&DS segment"))
    for y, (b, n, g, c, r, btb, src) in ICON.items():
        rows.append(dict(company="ICON", year=y, backlog_usd_bn=b, net_awards_usd_m=n, revenue_usd_m=r, book_to_bill=btb,
                         btb_basis="net business wins / revenue (published)", cancellation_rate=round(c / g, 3), source=src))
    df = pd.DataFrame(rows)
    df["collected"] = "2026-11-16"
    df.to_csv(OUT, index=False)
    print(df.groupby("company").book_to_bill.agg(["min", "max"]).round(2).to_string())


if __name__ == "__main__":
    main()
