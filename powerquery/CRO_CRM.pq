// CRO_CRM: Ergomed CRO opportunities (CRM export, EUR) -> common columns, USD (SIMULATED source)
let
    Source = Excel.Workbook(File.Contents(SourceFolder & "cro_crm.xlsx"), null, true),
    OpportunitiesSheet = Source{[Item = "Opportunities", Kind = "Sheet"]}[Data],
    PromotedHeaders = Table.PromoteHeaders(OpportunitiesSheet, [PromoteAllScalars = true]),
    TypedColumns = Table.TransformColumnTypes(PromotedHeaders, {
        {"Opportunity ID", type text}, {"Account Code", type text}, {"Account Name", type text}, {"Region", type text},
        {"Country", type text}, {"Therapeutic Area", type text}, {"Phase", type text}, {"Services", type text}, {"Stage", type text},
        {"Amount (EUR)", type number}, {"Probability (%)", type number}, {"Created Date", type date}, {"Proposal Submitted", type date},
        {"Award Date", type date}, {"Contract Signed", type date}, {"Closed Lost Date", type date}, {"Cancellation Date", type date},
        {"Loss Reason", type text}}),
    RenamedColumns = Table.RenameColumns(TypedColumns, {
        {"Opportunity ID", "source_id"}, {"Account Code", "client_code"}, {"Account Name", "client_name"}, {"Country", "country"},
        {"Therapeutic Area", "therapeutic_area"}, {"Phase", "detail"}, {"Services", "services"}, {"Stage", "source_stage"},
        {"Amount (EUR)", "value_local"}, {"Created Date", "created_date"}, {"Proposal Submitted", "proposal_date"},
        {"Award Date", "award_date"}, {"Contract Signed", "won_date"}, {"Closed Lost Date", "lost_date"},
        {"Cancellation Date", "cancel_date"}, {"Loss Reason", "loss_reason"}}),
    // region codes of the CRM -> group regions (docs/governance/mappings/region_map.csv)
    RegionMap = #table(type table [Region = text, region = text],
        {{"EU", "Europe"}, {"NA", "North America"}, {"APAC", "Asia-Pacific"}, {"ROW", "Rest of World"}}),
    JoinedRegion = Table.NestedJoin(RenamedColumns, {"Region"}, RegionMap, {"Region"}, "R", JoinKind.LeftOuter),
    MappedRegion = Table.RemoveColumns(Table.ExpandTableColumn(JoinedRegion, "R", {"region"}), {"Region"}),
    // a verbal award stays open: the group 'won' is the signed contract (mappings/stage_map.csv)
    StageMap = #table(type table [source_stage = text, common_stage = text, status = text], {
        {"Qualification", "1 Qualify", "Open"}, {"RFP Received", "2 Propose", "Open"}, {"Proposal Submitted", "2 Propose", "Open"},
        {"Bid Defense", "3 Negotiate", "Open"}, {"Awarded", "3 Negotiate", "Open"}, {"Contracted", "4 Won", "Won"},
        {"Cancelled", "4 Won", "Won"}, {"Closed Lost", "5 Lost", "Lost"}, {"No Bid", "6 Disqualified", "Disqualified"}}),
    JoinedStage = Table.NestedJoin(MappedRegion, {"source_stage"}, StageMap, {"source_stage"}, "S", JoinKind.LeftOuter),
    MappedStage = Table.ExpandTableColumn(JoinedStage, "S", {"common_stage", "status"}),
    // FX: ECB monthly average of the signature month (lost month for lost deals, last published month for open deals)
    LastRateMonth = List.Max(FX_Rates[month_start]),
    EventMonth = Table.AddColumn(MappedStage, "fx_month", each Date.StartOfMonth(
        if [won_date] <> null then [won_date] else if [lost_date] <> null then [lost_date] else LastRateMonth), type date),
    EurRates = Table.SelectRows(FX_Rates, each [currency] = "EUR"),
    JoinedRate = Table.NestedJoin(EventMonth, {"fx_month"}, EurRates, {"month_start"}, "FX", JoinKind.LeftOuter),
    ExpandedRate = Table.ExpandTableColumn(JoinedRate, "FX", {"rate_to_usd"}),
    ValueUSD = Table.AddColumn(ExpandedRate, "value_usd", each [value_local] * [rate_to_usd], type number),
    // duplicate check (DQ01): same account, amount, phase, area and contract date -> keep the first created
    SortedByCreation = Table.Buffer(Table.Sort(ValueUSD, {{"created_date", Order.Ascending}})),
    RemovedDuplicateWins = Table.Distinct(SortedByCreation, {"client_code", "value_local", "detail", "therapeutic_area", "won_date"}),
    AddedBusiness = Table.AddColumn(RemovedDuplicateWins, "business", each "Ergomed CRO", type text)
in
    AddedBusiness
