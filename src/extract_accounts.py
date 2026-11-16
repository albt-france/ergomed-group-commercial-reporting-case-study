"""PUBLIC DATA - Ergomed Group figures from the accounts filed at Companies House, with the page each figure comes from.

Why the figures are typed in, not parsed: the filed PDFs are scans (no text layer). src/pdf_text.py OCRs them so
pages can be searched; each figure below was then read on the rendered page (src/render_page.py) and typed in.
This script re-checks the arithmetic of every table (rows must add up to the printed totals) and writes:

  data/public/ergomed_revenue.csv        revenue by year x business x client region (GBP to FY2023, USD after)
  data/public/ergomed_commercial.csv     order book, net awards, revenue, implied book-to-bill
  data/public/reconciliation_public.csv  the same figure seen in two places, with the gap and the explanation

Entities: Ergomed plc, renamed Ergomed Group Limited (CH 04081094) after the take-private; from FY2024 the group is
consolidated by Eden TopCo Limited (CH 15049295). Scheme effective 13 Nov 2023, AIM cancellation 14 Nov 2023
(company announcements); acquisition by funds advised by Permira confirmed in the FY2023 and FY2025 accounts.
Figures are historical and dated; nothing here describes the company's current situation beyond these filings.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public"
CH = "https://find-and-update.company-information.service.gov.uk/company/{}/filing-history"
DOCS = {
    "AR2020": ("Ergomed plc Annual Report and Accounts 2020 (filed 29 Jun 2021)", "04081094"),
    "AR2021": ("Ergomed plc Annual Report and Accounts 2021 (filed 17 Jun 2022)", "04081094"),
    "AR2022": ("Ergomed plc Annual Report and Accounts 2022 (filed 4 Jul 2023)", "04081094"),
    "AR2019": ("Ergomed plc Annual Report and Accounts 2019 (filed 16 Jun 2020)", "04081094"),
    "FS2023": ("Ergomed Group Limited Annual Report and Financial Statements 2023 (filed 5 Oct 2024)", "04081094"),
    "TC2024": ("Eden TopCo Limited Annual Report, period to 31 Dec 2024 (filed 19 Jun 2025)", "15049295"),
    "TC2025": ("Eden TopCo Limited Annual Report and Financial Statements 2025 (filed 4 Jun 2026)", "15049295"),
}
COLLECTED = "2026-11-16"

# Revenue by client location x service line (note 2 'Geographical market and major service lines'), in thousands.
# (year, currency, months, doc, pdf_page, region -> (CRO, PV), printed totals (CRO, PV, Total))
REV = [
    (2019, "GBP", 12, "AR2020", 85, {"UK": (5096, 7590), "Rest of Europe, Middle East and Africa": (17427, 10910),
                                     "North America": (9245, 16337), "Asia": (1064, 445), "Australia": (10, 131)},
     (32842, 35413, 68255)),
    (2020, "GBP", 12, "AR2020", 85, {"UK": (3589, 8590), "Rest of Europe, Middle East and Africa": (10146, 13183),
                                     "North America": (15828, 30836), "Asia": (1753, 2269), "Australia": (0, 197)},
     (31316, 55075, 86391)),
    (2021, "GBP", 12, "AR2022", 94, {"UK": (5415, 8785), "Rest of Europe, Middle East and Africa": (9585, 12981),
                                     "North America": (38388, 36028), "Rest of World": (4689, 2710)},
     (58077, 60504, 118581)),
    (2022, "GBP", 12, "AR2022", 94, {"UK": (11593, 8642), "Rest of Europe, Middle East and Africa": (14537, 14726),
                                     "North America": (42238, 48323), "Rest of World": (2995, 2208)},
     (71363, 73899, 145262)),
    (2023, "GBP", 12, "FS2023", 31, {"UK": (7149, 10494), "Rest of Europe, Middle East and Africa": (22280, 15195),
                                     "North America": (49568, 51021), "Rest of World": (1805, 2556)},
     (80802, 79266, 160068)),
    (2024, "USD", 13.5, "TC2025", 32, {"UK": (2161, 13093), "Rest of Europe, Middle East and Africa": (52371, 27251),
                                       "North America": (58253, 79461), "Rest of World": (4690, 6995)},
     (117475, 126800, 244725)),   # printed total 244,725: see reconciliation R6
    (2025, "USD", 12, "TC2025", 32, {"UK": (2193, 11218), "Rest of Europe, Middle East and Africa": (35190, 24464),
                                     "North America": (50589, 87646), "Rest of World": (2955, 8595)},
     (90927, 131923, 222850)),
]

# Order book and net awards, GBP millions (narrative sections of the annual reports)
COMMERCIAL = [
    # year, order_book, ob_doc, ob_page, net_awards, aw_doc, aw_page, cro_ob, pv_ob, split_page
    (2018, 109.2, "AR2019", 25, None, None, None, None, None, None),
    (2019, 124.1, "AR2019", 25, None, None, None, 69.5, 54.6, "AR2020 p.28, p.31"),
    (2020, 193.0, "AR2020", 12, 117.8, "AR2021", 26, 113.2, 79.8, "AR2020 p.28, p.31"),
    (2021, 239.7, "AR2021", 26, 165.3, "AR2021", 26, None, None, None),
    (2022, 295.0, "AR2022", 34, None, None, None, None, None, None),
    (2023, 324.2, "FS2023", 4, None, None, None, None, None, None),
]
REVENUE_GBPM = {2018: None, 2019: 68.3, 2020: 86.4, 2021: 118.6, 2022: 145.3, 2023: 160.1}  # highlights / reviews


def check_revenue():
    rows, problems = [], []
    for year, ccy, months, doc, page, regions, printed in REV:
        cro = sum(v[0] for v in regions.values())
        pv = sum(v[1] for v in regions.values())
        for label, calc, pr in (("CRO", cro, printed[0]), ("PV", pv, printed[1]), ("Total", cro + pv, printed[2])):
            if calc != pr:
                problems.append((year, label, calc, pr))
        for region, (c, p) in regions.items():
            for business, v in (("Ergomed CRO (clinical research)", c), ("PrimeVigilance (pharmacovigilance)", p)):
                rows.append(dict(year=year, currency=ccy, period_months=months, client_region=region, business=business,
                                 revenue_thousands=v, source=DOCS[doc][0], pdf_page=page,
                                 source_url=CH.format(DOCS[doc][1]), collected=COLLECTED))
    return pd.DataFrame(rows), problems


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rev, problems = check_revenue()
    # The only accepted mismatch is the documented typo in the FY2025 note (R6). Anything else stops the script.
    unexpected = [p for p in problems if not (p[0] == 2024 and p[1] == "Total")]
    assert not unexpected, f"table does not add up: {unexpected}"
    rev.to_csv(OUT / "ergomed_revenue.csv", index=False)

    com = []
    for year, ob, obd, obp, aw, awd, awp, cro, pv, sp in COMMERCIAL:
        r = REVENUE_GBPM.get(year)
        prev = next((c[1] for c in COMMERCIAL if c[0] == year - 1), None)
        implied = round(ob - prev + r, 1) if prev and r else None
        com.append(dict(year=year, currency="GBP", order_book_m=ob, order_book_source=f"{DOCS[obd][0]}, PDF p.{obp}",
                        net_awards_m=aw, net_awards_source=f"{DOCS[awd][0]}, PDF p.{awp}" if aw else "not disclosed",
                        revenue_m=r, book_to_bill=round(aw / r, 2) if aw and r else None,
                        implied_awards_m=implied, implied_book_to_bill=round(implied / r, 2) if implied else None,
                        cro_order_book_m=cro, pv_order_book_m=pv, split_source=sp or ""))
    com = pd.DataFrame(com)
    if cro_pv := [(c.year, c.cro_order_book_m + c.pv_order_book_m, c.order_book_m) for c in com.itertuples()
                  if pd.notna(c.cro_order_book_m)]:
        for y, s, t in cro_pv:
            assert abs(s - t) < 0.15, f"order book split does not add up in {y}"
    com.to_csv(OUT / "ergomed_commercial.csv", index=False)

    r21 = com.set_index("year")
    rec = [
        ("R1", "Revenue FY2022, KPI table vs note 2", "GBP 145.3m (KPI table, AR2022 p.35)", "GBP 145,262k (note 2, p.94)",
         0.0, "Rounding only: same figure, millions vs thousands.", "Reconciled"),
        ("R2", "Order book roll-forward 2021", "Opening 193.0 + net awards 165.3 - revenue 118.6 = 239.7",
         "Closing order book 239.7 (AR2021 p.26)", round(193.0 + 165.3 - 118.6 - 239.7, 1),
         "Closes exactly: the published net awards are consistent with the order book and revenue.", "Reconciled"),
        ("R3", "Order book roll-forward 2020", "Opening 124.1 + net awards 117.8 - revenue 86.4 = 155.5",
         "Closing order book 193.0 (AR2020 p.12)", round(124.1 + 117.8 - 86.4 - 193.0, 1),
         "Gap of GBP 37.5m. Hypothesis (not confirmed in the filing): order books acquired with the two 2020 "
         "acquisitions and FX. Would need the acquired-backlog figure from the data owner.", "Open - hypothesis"),
        ("R4", "Revenue by region FY2021, highlights vs note", "UK & EMEA 36.9 + Asia 7.2 (AR2021 p.7)",
         "UK 14.2 + Rest of EMEA 22.6 + Rest of World 7.4 (AR2022 p.94)", round(36.9 + 7.2 - (14.200 + 22.566 + 7.399), 1),
         "Same total, different region boundaries: 'Asia' in the highlights vs 'Rest of World' in the note.",
         "Reconciled - mapping"),
        ("R5", "Region list 2019-2020 vs 2021+", "UK, REMEA, North America, Asia, Australia",
         "UK, REMEA, North America, Rest of World", 0.0,
         "Taxonomy change: Asia + Australia merged into Rest of World. Mapping table needed for a time series.",
         "Reconciled - mapping"),
        ("R6", "Revenue prior period (to Dec 2024), note 2 total vs its rows", "Printed total 244,725 (TC2025 p.32)",
         "Rows and income statement: 117,475 + 126,800 = 244,275 (TC2025 p.20)", 450.0,
         "Transposed digits in the printed total of the note; rows, the income statement and the narrative "
         "(USD 244.3m) agree on 244,275.", "Reconciled - source typo"),
        ("R7", "Comparability FY2023 -> FY2024", "FY2023: GBP, 12 months, Ergomed Group consolidated",
         "FY2024: USD, 13.5 months of Ergomed results, Eden TopCo consolidated", None,
         "Currency, period length and reporting entity all change. Not comparable without restating; "
         "growth rates across this break are not computed.", "Documented"),
        ("R8", "CRO service fee revenue FY2022", "GBP 50.8m (AR2022 p.36)",
         "CRO revenue 71,363 - reimbursable expenses 20,647 = 50,716 (p.96)", round(50.8 - 50.716, 2),
         "GBP 0.1m. Hypothesis: service fee = revenue minus reimbursable *revenue*, which the notes do not "
         "show separately from reimbursable *expenses*. Small, left open.", "Open - small"),
    ]
    pd.DataFrame(rec, columns=["id", "check", "figure_a", "figure_b", "gap", "explanation", "status"]).to_csv(
        OUT / "reconciliation_public.csv", index=False)
    print("revenue rows", len(rev), "| commercial", len(com), "| reconciliation items", len(rec),
          "| 2021 implied book-to-bill", r21.loc[2021, "book_to_bill"])


if __name__ == "__main__":
    main()
