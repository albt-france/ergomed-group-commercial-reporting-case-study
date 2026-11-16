# Sources (collected 16 Nov 2026)

## PUBLIC DATA
| Source | What | How | Licence / terms |
|---|---|---|---|
| Companies House, Ergomed Group Limited (04081094), formerly Ergomed plc | Annual reports and accounts FY2019-FY2023 (group), FY2024-FY2025 (company) | `src/collect_public.py`, public "View PDF" links, 3 s between requests | UK public register, free |
| Companies House, Eden TopCo Limited (15049295) | Group accounts for the period to 31 Dec 2024 and FY2025 (consolidates the group after the take-private) | same | same |
| Companies House, Ergomed Clinical Research Limited (05094681) | Accounts FY2022-FY2025 (UK trading entity), collected for context, not used in figures | same | same |
| Group websites (ergomedgroup.com, primevigilance.com, adamasconsulting.com) | Description of the businesses | `src/collect_public.py`, robots.txt checked | facts only, no text reused |
| ClinicalTrials.gov API v2 | 38,468 interventional industry-sponsored studies started 2019-2025; studies naming an Ergomed entity | `src/collect_trials.py` | US NLM, public domain |
| SEC EDGAR | 10-K (Medpace, IQVIA) and 20-F (ICON) filings FY2020-FY2025 | `src/collect_competitors.py`, generic user agent, 2 s between requests | public filings |
| ICON plc results releases (Form 6-K, company site) | FY2024 and FY2025 backlog, net wins, book-to-bill | cited in `src/extract_competitors.py` | public |
| ECB Data Portal | Monthly average EUR/USD and EUR/GBP reference rates | `src/collect_fx.py` | ECB, free reuse with source |

Company status, from the filed accounts: Ergomed plc was acquired by funds advised by Permira in November 2023 (scheme
effective 13 Nov 2023; AIM admission cancelled 14 Nov 2023, company announcements), then renamed Ergomed Group Limited.
All Ergomed figures are historical and dated; nothing is said about the company beyond these filings.
No person names are kept: the filings name directors and the trial registry names investigators; neither is extracted.

## SIMULATED
Everything in `data/simulated/` and `data/processed/` except the FX rates: see `data/ASSUMPTIONS.md`.
