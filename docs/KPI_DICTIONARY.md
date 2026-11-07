# KPI dictionary — Berlin accommodation benchmarking

**Grain:** One row per eligible property listing at the 19 September 2026 snapshot. The dataset is not a transaction table. All calculations are per listing and respond to district/capacity filters.

| KPI                      | Formula                                                                          | Unit               | Interpretation and caveat                                             |
| ------------------------ | -------------------------------------------------------------------------------- | ------------------ | --------------------------------------------------------------------- |
| Listing count            | Number of rows in `FactListing`                                                  | properties         | Eligible published listings, not all accommodation units in Berlin.   |
| Median asking price      | Median(`AskingPriceEUR`)                                                         | EUR / listed night | Middle asking price, not realised booking price.                      |
| P25                      | Inclusive 25th percentile of `AskingPriceEUR`                                    | EUR / listed night | One quarter of sample priced at or below approximately this value.    |
| P75                      | Inclusive 75th percentile                                                        | EUR / listed night | Three quarters of sample at or below approximately this value.        |
| Middle-half price spread | P75 – P25                                                                        | EUR / listed night | Descriptive dispersion; **not** a confidence interval.                |
| Average minimum stay     | Arithmetic mean of `MinimumNights`                                               | nights             | Advertised restriction, not booking duration.                         |
| Listings with reviews %  | Listings with `ReviewCount > 0` / all eligible listings                          | % of listings      | Presence of reviews only; **not** occupation or conversion.           |
| City median              | Median after removing only district filter                                       | EUR / listed night | Keeps capacity filter. Beware changes in composition.                 |
| District difference      | (District median − city median) / city median                                    | %                  | Relative listed-price comparison; not causal or an opportunity score. |
| Sample status            | 0 listings: No comparable listings; 1–19: Limited sample; 20+: Sufficient sample | label              | Practical warning based on sample size, not a statistical guarantee.  |

### Sample reconciliation checklist

Compare `COUNTROWS(FactListing)` in Power BI to `eligible_rows` in `build/quality_report.json`. Compare `DISTINCTCOUNT(FactListing[ListingID])` to `eligible_rows` in SQLite. Compare district counts in Power BI to `SELECT district, COUNT(*) ... GROUP BY district` from `sql/quality_checks.sql`. For the full unfiltered model, the median should match an independently calculated median of the exported `AskingPriceEUR` field; SQLite's `AVG` does **not** verify the median.

### Why medians and quartiles?

A few unusually expensive listings can pull the arithmetic average upward. Medians and quartiles give a more robust descriptive benchmark. This does **not** solve the comparability problem: similar guest capacity does not mean identical apartment quality.

### Why no time chart?

One snapshot cannot identify a market trend. An arbitrary chart by host creation date would not measure actual asking-price evolution. A later multi-snapshot analysis would need a new defined question and duplicate-listing handling.
