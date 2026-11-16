"""One-page ad hoc note for leadership: 'Why is Europe behind target this year?' (SIMULATED data).
Every number comes from data/processed/findings.json. Output: docs/adhoc/europe_behind_target.md"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def m(x):
    return f"{'-' if x < 0 else ''}${abs(x) / 1e6:,.1f}m"


def p(x):
    return f"{100 * x:.0f}%"


def main():
    fd = json.loads((P / "findings.json").read_text())
    e, k = fd["europe"], fd["kpi"]
    d, dn = e["decomposition"], e["decomposition_na"]
    ta = {r["ta"]: r for r in e["ta_win_rates"]}
    q = pd.read_csv(P / "an_oncology_quarterly.csv")
    reg = fd["by_region"]
    bus_eu = {r["business"]: r for r in fd["by_business_region"] if r["region"] == "Europe"}
    lines = [
        "# Why is Europe behind target? (ad hoc note, 13 Nov 2026)", "",
        "*SIMULATED, illustrative data - not Ergomed's pipeline. Requested by: commercial leadership. Time spent: half a day.*", "",
        "## Question, clarified",
        "Europe is the region furthest behind its new-business target in 2026. Is it a market problem, a pipeline problem or a "
        "conversion problem, and in which business? Scope: Jan-Oct 2026 vs the re-phased target and vs Jan-Oct 2025; group "
        "definitions (won = signed contract, USD at ECB monthly rates).", "",
        "## Method",
        "1. Locate the gap: region, then business x region (Power BI page *Targets & variance*).",
        "2. Decompose the gap of the business that drives it: won value = decisions x win rate x average deal (exact, vs last year).",
        "3. Drill the largest effect by therapeutic area and quarter; compare with North America (same business, same period).",
        "4. Rule out data causes first: late files, mapping, currency, duplicates (Data health page).", "",
        "## Findings (what the data shows)",
        f"- Europe: {m(reg['Europe']['won'])} won vs {m(reg['Europe']['target'])} target ({p(e['attainment'])}). Other large region: "
        f"North America {p(reg['North America']['won'] / reg['North America']['target'])}.",
        f"- The gap is in **CRO**: CRO Europe at {p(e['cro_eu_attainment'])} ({m(e['cro_eu_gap'])}); PV Europe at "
        f"{p(bus_eu['PrimeVigilance']['won'] / bus_eu['PrimeVigilance']['target'])}, ADAMAS Europe at "
        f"{p(bus_eu['ADAMAS']['won'] / bus_eu['ADAMAS']['target'])}.",
        f"- CRO Europe vs last year: volume {m(d['volume'])} (decisions {d['n_py']} -> {d['n_cy']}), **conversion {m(d['conversion'])}** "
        f"(win rate {p(d['wr_py'])} -> {p(d['wr_cy'])}), deal size {m(d['deal_size'])}. Same decomposition in North America: "
        f"conversion {m(dn['conversion'])}.",
        f"- The conversion drop is concentrated in **oncology**: {p(ta['Oncology']['wr_py'])} -> {p(ta['Oncology']['wr_ytd'])} "
        f"({ta['Oncology']['n_ytd']} decisions); rare disease {p(ta['Rare disease']['wr_py'])} -> {p(ta['Rare disease']['wr_ytd'])}. "
        f"North America oncology this year: {p(ta['Oncology']['wr_na_ytd'])}.",
        "- By quarter, Europe oncology: " + ", ".join(f"{r.quarter} {p(r.onc_eu)}" for r in q.itertuples())
        + f". Every 2026 quarter is at or below {p(q[q.quarter.str.startswith('2026')].onc_eu.max())}; 2025 averaged "
        f"{p(q[q.quarter.str.startswith('2025')].onc_eu.mean())} with one weak quarter (Q2), so one quarter alone is not a signal.",
        f"- Demand did not fall: oncology RFPs in Europe {e['onc_rfps_py']} (Jan-Oct 2025) -> {e['onc_rfps_cy']} (Jan-Oct 2026); "
        f"average opportunity {m(e['onc_avg_value_py'])} -> {m(e['onc_avg_value_cy'])}.",
        "- Data causes ruled out: no late CRO file, stage mapping applied (verbal awards excluded both years), FX at the same policy.", "",
        "## Hypotheses (not shown by the data, to check)",
        "- A competitor pricing more aggressively in European oncology bid defenses.",
        "- A change in the bid-defense team or in the oncology proposal template in early 2026.",
        "- A shift in sponsor mix (more large-pharma oncology bids, harder to win).",
        "- The CRM loss reasons ('Price', 'Competitor capability', ...) are too coarse to separate these.", "",
        "## Limitations",
        f"- {ta['Oncology']['n_ytd']} oncology decisions in Europe this year: 95% interval about +/- "
        f"{196 * (ta['Oncology']['wr_ytd'] * (1 - ta['Oncology']['wr_ytd']) / ta['Oncology']['n_ytd']) ** 0.5:.0f} points around {p(ta['Oncology']['wr_ytd'])}.",
        "- One year of comparison; the re-phased target is pending FP&A approval (as received, Europe is at the same level).",
        "- Simulated data: the pattern was planted to test the method; the method, not the number, is the deliverable.", "",
        "## Recommendation",
        "1. **This week**: review the last 10 European oncology bid-defense losses with the CRO business development lead "
        "(price position, competitor, team, feedback from the sponsor).",
        "2. **This month**: add a structured loss-reason field (competitor named, price gap %) to the CRM for bid defenses.",
        "3. **In the weekly report**: track Europe oncology win rate as an exception until it is back within 5 points of North America.",
    ]
    out = ROOT / "docs" / "adhoc" / "europe_behind_target.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("written", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
