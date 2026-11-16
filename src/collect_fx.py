"""PUBLIC DATA - ECB euro foreign exchange reference rates, monthly averages (EXR dataset, ECB Data Portal API).
USD per EUR and GBP per EUR -> rate_to_usd for EUR and GBP. Output: data/public/fx_rates_ecb.csv"""
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://data-api.ecb.europa.eu/service/data/EXR/M.{}.EUR.SP00.A?startPeriod=2024-01&format=csvdata"


def main():
    s = {}
    for c in ("USD", "GBP"):
        r = requests.get(URL.format(c), headers={"User-Agent": "IndependentCaseStudy research-bot"}, timeout=60)
        r.raise_for_status()
        d = pd.read_csv(StringIO(r.text))
        s[c] = d.set_index("TIME_PERIOD")["OBS_VALUE"]
    df = pd.DataFrame({"usd_per_eur": s["USD"], "gbp_per_eur": s["GBP"]}).dropna()
    rows = []
    for m, r in df.iterrows():
        rows += [dict(month=m, currency="EUR", rate_to_usd=round(r.usd_per_eur, 6)),
                 dict(month=m, currency="GBP", rate_to_usd=round(r.usd_per_eur / r.gbp_per_eur, 6)),
                 dict(month=m, currency="USD", rate_to_usd=1.0)]
    out = pd.DataFrame(rows)
    out["source"] = "ECB euro reference rates, monthly average (EXR, SP00.A)"
    out.to_csv(ROOT / "data" / "public" / "fx_rates_ecb.csv", index=False)
    print(df.tail(3).round(4).to_string(), "\nmonths:", len(df))


if __name__ == "__main__":
    main()
