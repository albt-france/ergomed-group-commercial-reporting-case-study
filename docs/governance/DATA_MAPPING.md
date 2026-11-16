# Data mapping

How three exports that do not look alike become one model (SIMULATED sources; rules in `src/prepare.py`, M version of the per-source steps in `powerquery/`).

## Sources

| Source | Owner | Format | Currency | Grain | Specifics |
|---|---|---|---|---|---|
| `cro_crm.xlsx` | CRO Sales Operations | CRM export, one sheet | EUR | opportunity | RFP and bid-defense stages; verbal award before contract |
| `pv_pipeline.csv` | PV BD Europe / North America / APAC & RoW | 3 regional trackers compiled | USD | contract | recurring: annual value x years |
| `adamas_tracker.xlsx` | ADAMAS Operations | manual Excel tracker | GBP | audit | merged cells, month banners, free-text status |
| `targets.xlsx` | FP&A | one sheet per year | USD | business x region x month | annual / 12 |
| `revenue_actuals.csv`, `order_book_opening.csv` | FP&A | finance extracts | USD | business x region x month | approved source |
| `clients_master.csv` | Commercial Operations | master data | - | client | one group id, a code per business |
| `fx_rates_ecb.csv` | ECB (PUBLIC DATA) | API | - | month x currency | monthly average reference rates |

## Field mapping

| Model column | CRO CRM | PV pipeline | ADAMAS tracker |
|---|---|---|---|
| `source_id` | Opportunity ID | deal_ref | Ref |
| `client_code` | Account Code | client_ref | (none: name) |
| `client_name` | Account Name | client | Client (merged cells, forward-filled) |
| `region` | Region (EU/NA/APAC/ROW) | country -> country_region_map.csv | Region (UK/EMEA/Americas/Asia) |
| `therapeutic_area` | Therapeutic Area | product_area | 'Not applicable (audit)' |
| `detail` | Phase | service | Audit type |
| `source_stage` | Stage | pipeline_status | Status (5 spellings normalised) |
| `value_local` | Amount (EUR) | tcv_usd = annual_value_usd x contract_years | Quote (GBP), number or '£12,500' text |
| `created_date` | Created Date | created_on | Requested (date or dd/mm/yyyy text) |
| `proposal_date` | Proposal Submitted | proposal_sent_on | Quote sent |
| `won_date` | Contract Signed | signed_on | Confirmed on ('TBC' -> quote date + 14 days, flagged) |
| `award_date` | Award Date (verbal, CRO only) | - | - |
| `lost_date` | Closed Lost Date | status_changed_on if Closed Lost | quote date + 14 days (no decline date in the tracker) |
| `cancel_date` | Cancellation Date | - | - |
| `data_owner` | CRO Sales Operations | tracker (PV BD Europe / North America / APAC & RoW) | ADAMAS Operations |

## Stage mapping (`mappings/stage_map.csv`)

| Business | Source stage | Common stage | Status | Note |
|---|---|---|---|---|
| Ergomed CRO | Qualification | 1 Qualify | Open | opportunity logged before an RFP |
| Ergomed CRO | RFP Received | 2 Propose | Open | proposal in preparation |
| Ergomed CRO | Proposal Submitted | 2 Propose | Open |  |
| Ergomed CRO | Bid Defense | 3 Negotiate | Open | shortlisted; bid defense meeting |
| Ergomed CRO | Awarded | 3 Negotiate | Open | verbal award: NOT a win until the contract is signed (8% are never contracted) |
| Ergomed CRO | Contracted | 4 Won | Won | contract signed = the group definition of a win |
| Ergomed CRO | Cancelled | 4 Won | Won | won then cancelled: counted as won at signature and as a cancellation at cancellation date |
| Ergomed CRO | Closed Lost | 5 Lost | Lost | includes verbal awards not contracted (loss reason 'Award not contracted') |
| Ergomed CRO | No Bid | 6 Disqualified | Disqualified | not in the win-rate denominator |
| PrimeVigilance | Lead | 1 Qualify | Open |  |
| PrimeVigilance | Qualified | 1 Qualify | Open |  |
| PrimeVigilance | Proposal Sent | 2 Propose | Open |  |
| PrimeVigilance | Negotiation | 3 Negotiate | Open |  |
| PrimeVigilance | Signed | 4 Won | Won | contract signed |
| PrimeVigilance | Closed Lost | 5 Lost | Lost | lost after a proposal; before a proposal -> 6 Disqualified (rule in prepare.py) |
| ADAMAS | Enquiry | 1 Qualify | Open |  |
| ADAMAS | Quoted | 2 Propose | Open | quote sent |
| ADAMAS | Confirmed | 4 Won | Won | booking confirmed by the client |
| ADAMAS | Declined | 5 Lost | Lost |  |
| ADAMAS | Withdrawn | 6 Disqualified | Disqualified | enquiry withdrawn before a quote |

PV rule: 'Closed Lost' without a proposal date = 6 Disqualified (lost at lead stage).

## Region mapping (`mappings/region_map.csv`, `mappings/country_region_map.csv`)

| Business | Source value | Region | Rule |
|---|---|---|---|
| Ergomed CRO | EU | Europe | CRM region code |
| Ergomed CRO | nan | North America | CRM region code |
| Ergomed CRO | APAC | Asia-Pacific | CRM region code |
| Ergomed CRO | ROW | Rest of World | CRM region code |
| ADAMAS | UK | Europe | tracker region |
| ADAMAS | EMEA | Europe | tracker region; Middle East and Africa cannot be separated (limitation, small) |
| ADAMAS | Americas | North America | tracker region |
| ADAMAS | Asia | Asia-Pacific | tracker region |
| PrimeVigilance | (country) | see country_region_map.csv | PV has no region field: derived from the client country |

## Clients

CRO account code and PV client ref are mapped to `group_client_id` through `clients_master.csv`; ADAMAS has no code and is matched on the normalised name. Codes missing from the master fall back on the name; anything still unmatched is kept as `UNMAPPED:<name>` and raised as check DQ10 to Commercial Operations.

## Currency

EUR and GBP are converted to USD at the ECB monthly average of the month of the event (signature, loss, or the data cut for open deals). The rate is stored on each row (`fx_rate`), so any figure can be re-derived.

## Cross-source rules

1. **Duplicate opportunity**: same account, amount, phase, area and contract date -> keep the first created (DQ01).
2. **Integrated CRO + PV deal**: 'Clinical + PV' in the CRM and a PV contract for the same client within 45 days -> the PV value is deducted from the CRO amount (DQ02). Match priority: PV origin names the CRO id > 'CRO referral' > nearest date.
3. **Late file**: a regional PV tracker received after the deadline replaces that region's rows at the next refresh (DQ05).
