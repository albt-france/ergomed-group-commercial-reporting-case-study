// PV_Pipeline: PrimeVigilance contracts (3 regional trackers compiled, USD) -> common columns (SIMULATED source)
let
    ReadCsv = (file as text) => Table.PromoteHeaders(Csv.Document(File.Contents(SourceFolder & file),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]), [PromoteAllScalars = true]),
    OnTimeFile = ReadCsv("pv_pipeline.csv"),
    // a regional tracker received after the deadline replaces that region's stale rows (DQ05, REPORTING_CALENDAR.md)
    LateFile = try ReadCsv("pv_pipeline_na_late.csv") otherwise null,
    CombinedFiles = if LateFile = null then OnTimeFile
        else Table.Combine({Table.SelectRows(OnTimeFile, each [tracker] <> "PV BD North America"), LateFile}),
    BlanksToNull = Table.ReplaceValue(CombinedFiles, "", null, Replacer.ReplaceValue, {"proposal_sent_on", "signed_on", "origin"}),
    TypedColumns = Table.TransformColumnTypes(BlanksToNull, {
        {"deal_ref", type text}, {"client_ref", type text}, {"client", type text}, {"country", type text}, {"product_area", type text},
        {"service", type text}, {"pipeline_status", type text}, {"annual_value_usd", type number}, {"contract_years", Int64.Type},
        {"tcv_usd", type number}, {"created_on", type date}, {"proposal_sent_on", type date}, {"signed_on", type date},
        {"status_changed_on", type date}, {"origin", type text}, {"tracker", type text}}, "en-US"),
    RenamedColumns = Table.RenameColumns(TypedColumns, {
        {"deal_ref", "source_id"}, {"client_ref", "client_code"}, {"client", "client_name"}, {"product_area", "therapeutic_area"},
        {"service", "detail"}, {"pipeline_status", "source_stage"}, {"tcv_usd", "value_local"}, {"annual_value_usd", "acv_usd"},
        {"created_on", "created_date"}, {"proposal_sent_on", "proposal_date"}, {"signed_on", "won_date"}, {"tracker", "data_owner"}}),
    // PV has no region field: region from the client country (mappings/country_region_map.csv)
    CountryRegion = Table.PromoteHeaders(Csv.Document(File.Contents(MappingFolder & "country_region_map.csv")), [PromoteAllScalars = true]),
    JoinedRegion = Table.NestedJoin(RenamedColumns, {"country"}, CountryRegion, {"country"}, "C", JoinKind.LeftOuter),
    AddedRegion = Table.ExpandTableColumn(JoinedRegion, "C", {"region"}),
    LostDate = Table.AddColumn(AddedRegion, "lost_date", each if [source_stage] = "Closed Lost" then [status_changed_on] else null, type date),
    // stage mapping; lost before any proposal = disqualified (not in the win-rate denominator)
    CommonStage = Table.AddColumn(LostDate, "common_stage", each
        if [source_stage] = "Signed" then "4 Won"
        else if [source_stage] = "Closed Lost" then (if [proposal_date] = null then "6 Disqualified" else "5 Lost")
        else if [source_stage] = "Negotiation" then "3 Negotiate"
        else if [source_stage] = "Proposal Sent" then "2 Propose" else "1 Qualify", type text),
    ValueUSD = Table.AddColumn(CommonStage, "value_usd", each [value_local], type number),
    AddedBusiness = Table.AddColumn(ValueUSD, "business", each "PrimeVigilance", type text)
in
    AddedBusiness
