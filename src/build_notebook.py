"""Build and execute the single notebook notebooks/market_and_public_data.ipynb (PUBLIC DATA only):
1. Ergomed Group in its filed accounts (revenue by business and region, order book, reconciliation)
2. The market it sells into: ClinicalTrials.gov, oncology and rare disease, phase, country, sponsor size
3. Competitor benchmarks: backlog and book-to-bill of listed CROs
Usage: python src/build_notebook.py"""
from pathlib import Path

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "market_and_public_data.ipynb"

cells = [
    ("md", "# Ergomed Group: public data and market view\n\nPUBLIC DATA only (Companies House filings, ClinicalTrials.gov API v2, "
           "SEC filings, ECB). Collected 16 Nov 2026 by the scripts in `src/`. Figures on Ergomed are historical and dated; "
           "no person names are kept.\n\nIndependent case study based on public data · not affiliated with or endorsed by Ergomed Group."),
    ("code", "import json\nimport pandas as pd\nimport matplotlib.pyplot as plt\nfrom pathlib import Path\n"
             "PUB = Path('..') / 'data' / 'public'\nplt.rcParams.update({'figure.figsize': (8, 3.6), 'axes.spines.top': False, "
             "'axes.spines.right': False, 'font.size': 9})\nBLUE, GREY, GREEN = '#2A78D6', '#C9C7BF', '#1BAF7A'"),
    ("md", "## 1. Ergomed Group in its filed accounts\nRevenue by service line (CRO = Ergomed CRO, PV = PrimeVigilance) as printed in "
           "note 2 of each filing. GBP to FY2023 (Ergomed plc / Ergomed Group Limited); USD from the period to Dec 2024 "
           "(Eden TopCo Limited, 13.5 months of Ergomed results). The two currency blocks are not joined: no growth rate is "
           "computed across the break."),
    ("code", "rev = pd.read_csv(PUB / 'ergomed_revenue.csv')\n"
             "t = rev.pivot_table(index=['year', 'currency', 'period_months'], columns='business', values='revenue_thousands', aggfunc='sum') / 1000\n"
             "t['Total'] = t.sum(axis=1); t['PV share'] = t.iloc[:, 1] / t['Total']\nt.round(2)"),
    ("code", "fig, axes = plt.subplots(1, 2, gridspec_kw={'width_ratios': [5, 2]})\n"
             "for ax, ccy in zip(axes, ['GBP', 'USD']):\n"
             "    d = t.xs(ccy, level='currency').droplevel('period_months')\n"
             "    d.iloc[:, :2].plot.bar(stacked=True, ax=ax, color=[BLUE, GREEN], width=0.7, legend=ccy == 'GBP')\n"
             "    ax.set_title(f'Revenue, {ccy} m'); ax.set_xlabel('')\n"
             "axes[1].set_xticklabels(['to Dec 2024\\n(13.5 m)', '2025'], rotation=0)\nplt.tight_layout()"),
    ("code", "reg = rev.groupby(['year', 'client_region']).revenue_thousands.sum().unstack()\n(reg.div(reg.sum(axis=1), axis=0) * 100).round(1)"),
    ("md", "Order book and net awards (GBP m, narrative sections of the annual reports). Book-to-bill = net awards / revenue; "
           "'implied' awards = change in order book + revenue (ignores acquisitions and FX)."),
    ("code", "com = pd.read_csv(PUB / 'ergomed_commercial.csv')\ncom[['year', 'order_book_m', 'net_awards_m', 'revenue_m', 'book_to_bill', 'implied_awards_m', 'implied_book_to_bill', 'cro_order_book_m', 'pv_order_book_m']]"),
    ("md", "### Reconciliation of the public figures\nThe same figure read in two places of the filings: what matches, what does not, and why."),
    ("code", "pd.set_option('display.max_colwidth', 120)\npd.read_csv(PUB / 'reconciliation_public.csv')[['id', 'check', 'gap', 'status', 'explanation']]"),
    ("md", "## 2. The market Ergomed sells into (ClinicalTrials.gov)\nInterventional studies with an industry lead sponsor, started "
           "2019-2025. Oncology = MeSH Neoplasms in the registry's condition index; rare disease = proxy (MeSH inborn genetic "
           "diseases, or 'rare' / 'orphan' in conditions or keywords). Sponsor size = studies started by the lead sponsor in the window."),
    ("code", "s = json.loads((PUB / 'ct_summary.json').read_text())\n{k: s[k] for k in ['studies', 'focus_studies', 'focus_share', 'small_mid_share_focus', 'small_mid_share_other', 'phase2_3_share_focus']}"),
    ("code", "y = pd.read_csv(PUB / 'ct_by_year.csv', index_col=0)\nax = y[['Oncology', 'Rare disease', 'Oncology + rare']].plot.bar(stacked=True, color=[BLUE, GREEN, '#86B6EF'], width=0.7)\n"
             "ax.set_title('Industry-sponsored oncology and rare-disease studies started per year'); ax.set_xlabel('')\nplt.tight_layout()"),
    ("code", "ps = pd.read_csv(PUB / 'ct_by_phase_size.csv', index_col=0)\nps = ps.loc[[p for p in ['Phase I', 'Phase II', 'Phase III', 'Phase IV'] if p in ps.index]]\n"
             "(ps.div(ps.sum(axis=1), axis=0) * 100).round(1)"),
    ("code", "c = pd.read_csv(PUB / 'ct_by_country.csv', index_col=0).head(15)\nax = c.studies[::-1].plot.barh(color=[BLUE if r == 'Europe' else GREY for r in c.region[::-1]])\n"
             "ax.set_title('Oncology / rare-disease studies by country (blue = Europe)'); plt.tight_layout()"),
    ("code", "pd.read_csv(PUB / 'ct_ergomed.csv').groupby(['role', 'phase']).size()"),
    ("md", "## 3. Competitor benchmarks (listed CROs)\nDefinitions differ (see `src/extract_competitors.py`); ICON changed its backlog "
           "method on 1 Oct 2025. Compare direction, not decimals."),
    ("code", "comp = pd.read_csv(PUB / 'competitors.csv')\ncomp.pivot(index='year', columns='company', values='book_to_bill').round(2)"),
    ("code", "ax = comp.pivot(index='year', columns='company', values='book_to_bill').plot(marker='o')\nax.axhline(1, color=GREY, ls='--')\n"
             "ax.set_title('Book-to-bill, listed CROs'); plt.tight_layout()"),
    ("md", "**Findings** - Oncology and rare disease are about a fifth of industry-sponsored interventional studies, and most "
           "of them are run by small and mid-size sponsors, the usual clients of a specialist mid-size CRO. Listed CROs reported "
           "book-to-bill between 1.0x and 1.2x in 2024-2025.\n\n**Limitations** - the rare-disease flag is a proxy; sponsor size "
           "is measured by trial count, not revenue; registry data lag the real start of studies."),
]


def main():
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in cells]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    ExecutePreprocessor(timeout=300, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(NB.parent)}})
    NB.write_text(nbf.writes(nb), encoding="utf-8")
    print("notebook executed:", NB.relative_to(ROOT))


if __name__ == "__main__":
    main()
