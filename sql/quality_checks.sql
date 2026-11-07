-- Run against build/market.sqlite using the SQLite command line or DB Browser.
-- Every comparison should return zero rows (except the summary SELECTs).

SELECT exclusion_reason, COUNT(*) AS records
FROM listing_audit
GROUP BY exclusion_reason
ORDER BY records DESC;

-- Source-to-output reconciliation.
SELECT
    (SELECT COUNT(*) FROM listing_audit) AS source_rows,
    (SELECT COUNT(*) FROM fact_listing) AS included_rows,
    (SELECT COUNT(*) FROM listing_audit WHERE exclusion_reason <> 'eligible') AS excluded_rows;

-- Duplicate fact identifiers are unacceptable.
SELECT listing_id, COUNT(*) AS n
FROM fact_listing
GROUP BY listing_id
HAVING COUNT(*) <> 1;

-- All fact keys must have a matching dimension row.
SELECT f.listing_id FROM fact_listing AS f
LEFT JOIN dim_district AS d ON f.district_id = d.district_id
WHERE d.district_id IS NULL;

SELECT f.listing_id FROM fact_listing AS f
LEFT JOIN dim_capacity AS c ON f.capacity = c.capacity
WHERE c.capacity IS NULL;

-- Exact accounting, in integer cents; Power BI shows euros.
SELECT d.district, COUNT(*) AS listings,
       ROUND(AVG(f.asking_price_cents) / 100.0, 2) AS mean_asking_price_eur
FROM fact_listing AS f
JOIN dim_district AS d ON f.district_id = d.district_id
GROUP BY d.district
ORDER BY listings DESC;
