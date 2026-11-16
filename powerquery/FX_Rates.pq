// FX_Rates: ECB monthly average reference rates (PUBLIC DATA) -> rate to USD by month and currency
let
    Source = Csv.Document(File.Contents(SourceFolder & "fx_rates_ecb.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    TypedColumns = Table.TransformColumnTypes(PromotedHeaders, {{"month", type text}, {"currency", type text}, {"rate_to_usd", type number}}, "en-US"),
    MonthAsDate = Table.AddColumn(TypedColumns, "month_start", each Date.FromText([month] & "-01"), type date),
    KeptColumns = Table.SelectColumns(MonthAsDate, {"month_start", "currency", "rate_to_usd"})
in
    KeptColumns
