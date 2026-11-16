// Targets: FP&A targets as received (one sheet per year, annual / 12) -> long table business x region x month
let
    Source = Excel.Workbook(File.Contents(SourceFolder & "targets.xlsx"), null, true),
    YearSheets = Table.SelectRows(Source, each [Kind] = "Sheet" and Text.StartsWith([Item], "FY")),
    PromotedEach = Table.TransformColumns(YearSheets, {{"Data", each Table.PromoteHeaders(_, [PromoteAllScalars = true])}}),
    Combined = Table.Combine(PromotedEach[Data]),
    UnpivotedMonths = Table.UnpivotOtherColumns(Combined, {"Business", "Region", "FY target (USD)"}, "month_label", "target_flat_usd"),
    MonthDate = Table.AddColumn(UnpivotedMonths, "month", each Date.FromText("01-" & [month_label], [Format = "dd-MMM-yy", Culture = "en-US"]), type date),
    Typed = Table.TransformColumnTypes(MonthDate, {{"target_flat_usd", type number}, {"FY target (USD)", type number}}),
    Renamed = Table.RenameColumns(Typed, {{"Business", "business"}, {"Region", "region"}, {"FY target (USD)", "fy_target_usd"}}),
    // re-phasing (month-in-quarter profile of last year's wins) is done in src/prepare.py, pending FP&A approval (DQ13)
    Kept = Table.SelectColumns(Renamed, {"business", "region", "month", "target_flat_usd", "fy_target_usd"})
in
    Kept
