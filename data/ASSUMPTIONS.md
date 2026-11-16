# Simulation assumptions (SIMULATED data)

The commercial dataset is **illustrative**: it is not Ergomed's pipeline, clients or targets. Clients are anonymous
("Sponsor 014"). It is built by `src/simulate.py` (seed 42) to do the job described in the vacancy on realistic material.

## Calibration on public orders of magnitude
| Parameter | Value in the simulation | Public anchor |
|---|---|---|
| Business mix | PV new business slightly above CRO; ADAMAS small | Group revenue by service line: PV 59%, CRO 41% in 2025 (Eden TopCo accounts, note 2) |
| Client regions | North America 54%, Europe 33%, Asia-Pacific 8%, Rest of World 5% | Revenue by client location 2025: North America 62%, UK + rest of EMEA 33%, rest of world 5% |
| Book-to-bill | 1.0x-1.2x by business | Listed CROs FY2025: Medpace 1.05x, ICON 1.09x, IQVIA R&DS ~1.18x implied (data/public/competitors.csv) |
| CRO focus | oncology 48%, rare disease 32% of CRO opportunities | the group describes its CRO as specialised in oncology and rare disease (group website, annual reports) |
| Currencies | CRO in EUR, PV in USD, ADAMAS in GBP; group reporting in USD | the group reports in USD since FY2024 (Eden TopCo accounts) |
| FX | ECB monthly averages (real rates) | ECB Data Portal, EXR dataset |

## Volumes and behaviour (24 months: Nov 2024 - Oct 2026, plus week 45 of 2026)
- ~380 CRO opportunities a year (RFI -> RFP -> proposal -> bid defense -> verbal award -> contract); 10% no bid; 70% of
  proposals reach a bid defense; 47% of bid defenses won; 8% of verbal awards never contracted; 3% of contracts cancelled.
- ~430 PV deals a year (lead -> qualified -> proposal -> negotiation -> signed); annual value lognormal (median ~USD 280k),
  1-5 years.
- ~560 ADAMAS audit enquiries a year; quote median ~GBP 27k; 66% of quotes confirmed.
- Pipeline growth 8% a year (5% for ADAMAS). Decisions due within 45 days of a quarter end are pulled to its last week
  (p = 0.5 CRO / PV, 0.3 ADAMAS); August decisions slip to September (p = 0.35).
- Targets: expected new business of each business x region (24 Monte-Carlo runs of the generators, without the planted
  drop), split annual / 12 as received from FP&A.

## Planted issues (answer key `data/_hidden_truth.csv`, read only by `src/check_truth.py` at the end)
1. Integrated CRO + PV deal booked in both systems (7 deals). 2. Stage names that do not match ('Awarded' vs 'Signed').
3. EUR, USD and GBP summed. 4. One large CRO win keyed twice. 5. PV North America file late in week 45.
6. Targets phased flat on a seasonal business. 7. Europe behind target, true cause: oncology bid-defense win rate in
CRO Europe falls from 0.47 to 0.10 from March 2026. 8. False signal: the quarter-end peak, present every quarter.

Result: 8/8 found by the pipeline (`data/processed/truth_check.csv`).
