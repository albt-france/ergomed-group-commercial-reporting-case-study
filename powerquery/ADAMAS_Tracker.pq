// ADAMAS_Tracker: manual audit tracker (GBP, merged cells, month banners, free-text status) -> common columns (SIMULATED)
let
    Source = Excel.Workbook(File.Contents(SourceFolder & "adamas_tracker.xlsx"), null, true),
    TrackerSheet = Source{[Item = "Audit tracker", Kind = "Sheet"]}[Data],
    SkippedTitleRows = Table.Skip(TrackerSheet, 3),
    PromotedHeaders = Table.PromoteHeaders(SkippedTitleRows, [PromoteAllScalars = true]),
    // month banners ("NOVEMBER 2024", merged across the row) have no audit reference
    RemovedMonthBanners = Table.SelectRows(PromotedHeaders, each [Ref] <> null and Text.StartsWith(Text.From([Ref]), "ADM-")),
    // merged client cells: the name is on the first row of the block only
    FilledDownClient = Table.FillDown(RemovedMonthBanners, {"Client"}),
    CleanStatus = Table.TransformColumns(FilledDownClient, {{"Status", each
        let s = Text.Lower(Text.Trim(Text.From(_))) in
        if s = "conf" or s = "confirmed" then "Confirmed" else if s = "declined" then "Declined"
        else if s = "withdrawn" then "Withdrawn" else if s = "quoted" then "Quoted" else "Enquiry", type text}}),
    // quote typed as a number or as text with a currency sign
    CleanQuote = Table.TransformColumns(CleanStatus, {{"Quote (GBP)", each
        if _ is number then _ else Number.From(Text.Select(Text.From(_), {"0".."9", "."})), type number}}),
    // dates: real Excel dates, dd/mm/yyyy text, or TBC
    ToDate = (v) => if v = null or (v is text and Text.Upper(Text.Trim(v)) = "TBC") then null
        else if v is text then Date.FromText(v, [Format = "dd/MM/yyyy", Culture = "en-GB"]) else Date.From(v),
    CleanDates = Table.TransformColumns(CleanQuote, {{"Requested", ToDate, type date}, {"Quote sent", ToDate, type date},
        {"Confirmed on", ToDate, type date}}),
    // a confirmed booking without a date (TBC): provisional date = quote date + 14 days, flagged (DQ07)
    FlagTBC = Table.AddColumn(CleanDates, "confirmed_tbc", each [Status] = "Confirmed" and [Confirmed on] = null, type logical),
    WonDate = Table.AddColumn(FlagTBC, "won_date", each if [Status] <> "Confirmed" then null
        else if [Confirmed on] <> null then [Confirmed on] else Date.AddDays([Quote sent], 14), type date),
    RegionMap = #table(type table [Region = text, region = text],
        {{"UK", "Europe"}, {"EMEA", "Europe"}, {"Americas", "North America"}, {"Asia", "Asia-Pacific"}}),
    JoinedRegion = Table.NestedJoin(WonDate, {"Region"}, RegionMap, {"Region"}, "R", JoinKind.LeftOuter),
    MappedRegion = Table.ExpandTableColumn(JoinedRegion, "R", {"region"}),
    RenamedColumns = Table.RenameColumns(MappedRegion, {{"Ref", "source_id"}, {"Client", "client_name"}, {"Audit type", "detail"},
        {"Requested", "created_date"}, {"Quote sent", "proposal_date"}, {"Quote (GBP)", "value_local"}, {"Status", "source_stage"}}),
    GbpRates = Table.SelectRows(FX_Rates, each [currency] = "GBP"),
    LastRateMonth = List.Max(GbpRates[month_start]),
    EventMonth = Table.AddColumn(RenamedColumns, "fx_month", each Date.StartOfMonth(if [won_date] <> null then [won_date] else LastRateMonth), type date),
    JoinedRate = Table.NestedJoin(EventMonth, {"fx_month"}, GbpRates, {"month_start"}, "FX", JoinKind.LeftOuter),
    ExpandedRate = Table.ExpandTableColumn(JoinedRate, "FX", {"rate_to_usd"}),
    ValueUSD = Table.AddColumn(ExpandedRate, "value_usd", each [value_local] * [rate_to_usd], type number),
    AddedBusiness = Table.AddColumn(ValueUSD, "business", each "ADAMAS", type text)
in
    AddedBusiness
