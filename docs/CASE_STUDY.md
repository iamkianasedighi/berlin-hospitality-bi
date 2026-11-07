# Case study | Berlin accommodation asking-price benchmarking

**Stakeholder:** Pricing/operations lead at a hypothetical small Berlin accommodation operator  
**Data snapshot:** 19 September 2026  
**Output:** Two-page Power BI report, a reusable local preparation workflow and documented quality checks

## The decision

A property manager reviewing advertised nightly prices needs a reference point for similar accommodation. One competing listing is too arbitrary; an overall city median can also be misleading when larger and smaller properties are mixed together.

The question is deliberately narrow: **What are comparable entire-home listings asking, by district and guest capacity, and how much evidence supports the comparison?**

## Scope and method

I used the public Inside Airbnb Berlin detailed-listings snapshot from 19 September 2026. The predefined comparison group contains entire-home listings for 1–6 guests, with asking prices of €30–€500 and advertised minimum stays of 1–30 nights.

A small Python script parses the source, applies those rules and records an exclusion reason for each rejected row. SQLite stores the audit and curated fact/dimension tables. Key, count and export checks run before the data is used in Power BI.

Power Query imports the exported CSVs. The semantic model contains a listing fact table and district/capacity dimensions with one-to-many relationships. Ten DAX measures calculate counts, median asking price, quartiles, a capacity-aware city benchmark and a small-sample flag.

## Data quality result

The local run processed **12,376 source rows**. **4,042** met the specified scope and **8,334** were excluded. The audit reconciled those totals; the fact table had 4,042 distinct IDs, no null prices and no orphan district or capacity references. Four automated pipeline tests also passed.

Exclusion reasons are applied in sequence, so their reported counts identify the **first applicable reason**, not every possible issue in a row.

## What the report showed

**Overall eligible sample:** Median asking price **€164.69**, with P25 **€123.23** and P75 **€226.50**. The middle-half spread is **€103.27**.

**Mitte, across eligible capacities:** **962 listings** with a median asking price of **€182.80**. This is descriptive; differences in guest-capacity mix can affect district comparisons.

**Mitte, two guests:** **271 listings** with P25 **€110.22**, median **€149.50**, and P75 **€197.37**. The district's two-guest median was about **8.5% above** the citywide median for the same capacity.

**A small-sample example:** Charlottenburg-Wilmersdorf, one guest, had **17 listings**, median **€85.00**. The report correctly showed **Limited sample** under the project's 20-listing threshold.

## What the manager can do with it

The second report page lets the manager select a district and a guest capacity, see the peer group's asking-price distribution and check the listing count. If an operator's own rate falls far outside this advertised range, the team has a reason to investigate the comparison more closely—not an automatic instruction to raise or lower its price.

This is the distinction between a business benchmark and a pricing engine: the report helps **structure a pricing discussion**, but it does not optimize price or estimate demand.

## Why these design choices

- **Median and quartiles, not only average:** Individual premium listings can skew the mean; P25/P50/P75 give a more useful descriptive view of the range.
- **District plus capacity:** This controls for one obvious difference between listings without pretending properties are otherwise identical.
- **Sample-size warning:** Fewer than 20 comparable listings get a visible caution. The cutoff is a practical reporting rule, not a statistical guarantee.
- **One fixed snapshot:** This makes local results reproducible; a rebuild is not presented as a live market update.
- **Small stack:** Python, SQLite, Power Query and Power BI were sufficient. There was no reason to add cloud infrastructure, APIs or machine learning.

## Limits and follow-up

Published asking prices are not realised booking prices. The source does not establish occupancy, revenue or profit, and it does not capture every property characteristic relevant to pricing. The selected filters also narrow coverage. One snapshot cannot support claims about time trends or seasonal change.

The next business step would be to compare the operator's **own** property attributes and asking prices with the relevant peer groups, with human review of amenity and quality differences. That would require additional internal data, which this portfolio project does not claim to have.

**Source:** [Inside Airbnb — Berlin detailed listings, 19 Sep 2026](https://insideairbnb.com/get-the-data/)
