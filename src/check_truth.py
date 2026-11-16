"""Final check (run last): did the governed pipeline find the 8 planted issues? Compares what src/prepare.py and
src/analysis.py detected with the answer key data/_hidden_truth.csv (written by src/simulate.py, never read before).
Output: data/processed/truth_check.csv"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def main():
    truth = pd.read_csv(ROOT / "data" / "_hidden_truth.csv")
    f = pd.read_csv(P / "fact_opportunity.csv")
    dq = pd.read_csv(P / "dq_issues.csv")
    fd = json.loads((P / "findings.json").read_text())
    rows = []

    t1 = truth[truth.issue == 1]
    pairs = {tuple(r.split(" / ")) for r in t1.record}
    found = {(a, b) for a, b in zip(f.source_id, f.get("cross_sell_with", pd.Series(dtype=str)))} if "cross_sell_with" in f else set()
    xs = f[f.is_cross_sell]
    hit = sum(1 for a, b in pairs if a in set(xs.source_id) and b in set(xs.source_id))
    rows.append((1, "Cross-sell deal counted twice", f"{hit}/{len(pairs)} pairs matched", hit == len(pairs)))

    rows.append((2, "Stage names do not match", f"naive win rate {fd['data_issues']['naive_win_rate']:.0%} vs governed "
                 f"{fd['data_issues']['governed_win_rate']:.0%}; {fd['data_issues']['award_not_contracted_rate']:.0%} of CRO verbal awards never contracted",
                 dq[dq.check_id == "DQ04"].rows_flagged.sum() == 0))
    rows.append((3, "Currencies summed as if equal", f"FX effect {fd['data_issues']['fx_effect'] / 1e6:+.1f}m USD on Jan-Oct 2026",
                 (f.currency != "USD").any() and abs(fd["data_issues"]["fx_effect"]) > 0))
    t4 = truth[truth.issue == 4].iloc[0]
    dup_id = t4.record.split(" / ")[1]
    rows.append((4, "Large win entered twice", f"{dup_id} excluded: {dup_id not in set(f.source_id)}", dup_id not in set(f.source_id)))
    t5 = truth[truth.issue == 5].iloc[0]
    late = dq[dq.check_id == "DQ05"]
    n5 = len(str(t5.record).split(";"))
    rows.append((5, "Late data owner", f"DQ05 {late.data_owner.iloc[0]}: {late.rows_flagged.iloc[0]} deals flagged (truth {n5})",
                 len(late) == 1 and late.rows_flagged.iloc[0] == n5))
    ph = fd["phasing"]
    rows.append((6, "Flat target on a seasonal business", f"last month of quarter holds {ph['m3_share_avg']:.0%} on average (flat 33%); "
                 f"mid-quarter attainment {ph['mid_quarter_att_flat']:.0%} flat vs {ph['mid_quarter_att_phased']:.0%} re-phased",
                 ph["m3_share_avg"] > 0.36))
    eu = fd["europe"]
    onc = next(r for r in eu["ta_win_rates"] if r["ta"] == "Oncology")
    d = eu["decomposition"]
    rows.append((7, "Europe behind target: oncology conversion", f"Europe {eu['attainment']:.0%}; conversion effect {d['conversion'] / 1e6:+.1f}m, "
                 f"oncology win rate {onc['wr_py']:.0%} -> {onc['wr_ytd']:.0%}",
                 min(fd["by_region"], key=lambda r: fd["by_region"][r]["won"] / fd["by_region"][r]["target"]
                     if fd["by_region"][r]["won"] > 50e6 else 9) == "Europe" and d["conversion"] < 0 and onc["wr_ytd"] < onc["wr_py"] - 0.1))
    qe = fd["quarter_end"]
    rows.append((8, "False signal: quarter-end spike", f"last week holds {qe['min_share']:.0%}-{qe['max_share']:.0%} of every quarter "
                 f"(uniform {qe['uniform_share']:.0%}); Q3 2026 {qe['q3_2026_share']:.0%}: within the usual range",
                 qe["min_share"] > 2 * qe["uniform_share"] and qe["min_share"] <= qe["q3_2026_share"] <= qe["max_share"]))
    out = pd.DataFrame(rows, columns=["issue", "name", "evidence", "found"])
    out.to_csv(P / "truth_check.csv", index=False)
    print(out[["issue", "found", "evidence"]].to_string(index=False))
    print(f"found {out.found.sum()}/8")


if __name__ == "__main__":
    main()
