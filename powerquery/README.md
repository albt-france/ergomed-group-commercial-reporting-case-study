# Power Query (M) - per-source shaping

These queries reproduce, in Power Query, the per-source steps of `src/prepare.py`, so a business user can refresh the
three sources without Python. Each step has a name that says what it does. Parameters: `SourceFolder` (raw files),
`MappingFolder` (docs/governance/mappings) and the `FX_Rates` query.

| Query | Source | Main steps |
|---|---|---|
| `CRO_CRM.pq` | cro_crm.xlsx (EUR) | promote headers, type, map region code, map stage, convert EUR to USD, keep the first of duplicates |
| `PV_Pipeline.pq` | pv_pipeline.csv + late regional file | late file replaces the stale region rows, region from country, map stage |
| `ADAMAS_Tracker.pq` | adamas_tracker.xlsx (GBP) | skip title rows, drop month banners, fill down merged client cells, clean status / quote / dates |
| `FX_Rates.pq` | fx_rates_ecb.csv | monthly ECB rate to USD per currency |
| `Targets.pq` | targets.xlsx | unpivot months; target as received (annual / 12) |

Kept in Python (`src/prepare.py`), and why: the cross-source steps that need a review log - duplicate detection across
records, the CRO / PV cross-sell matching (by client and date window, with a priority order), the reconciliation report
and the quality checks with owners. They run before the Power BI refresh; the model reads their output (`data/processed/`).

Status: the M files follow the same rules but were not refreshed in Power BI Desktop in this repository (the model
reads the processed files). Treat them as the migration path and test them before use.
