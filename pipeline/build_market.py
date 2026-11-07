"""Build a Berlin asking-price benchmark from one Inside Airbnb snapshot."""

import argparse
import csv
import gzip
import hashlib
import json
import re
import sqlite3
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SNAPSHOT = "2026-09-19"
SOURCE = ("https://data.insideairbnb.com/germany/be/berlin/"
          f"{SNAPSHOT}/data/listings.csv.gz")
REQUIRED = {"id", "room_type", "neighbourhood_group_cleansed", "accommodates",
            "price", "minimum_nights", "number_of_reviews"}
PRICE_PATTERN = re.compile(r"^(?:[€$]\s*)?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$", re.ASCII)


DISTRICT_NAMES = {
    "Charlottenburg-Wilm.": "Charlottenburg-Wilmersdorf",
    "Marzahn - Hellersdorf": "Marzahn-Hellersdorf",
    "Steglitz - Zehlendorf": "Steglitz-Zehlendorf",
    "Tempelhof - Schöneberg": "Tempelhof-Schöneberg",
    "Treptow - Köpenick": "Treptow-Köpenick",
}


def parse_price(raw):
    """Inside Airbnb uses local currency; '$' can be an export artifact."""
    text = (raw or "").strip()
    if not PRICE_PATTERN.fullmatch(text):
        return None
    try:
        value = Decimal(text.lstrip("€$").strip().replace(",", ""))
        return int(value * 100) if value.is_finite() else None
    except InvalidOperation:
        return None


def parse_int(raw):
    text = (raw or "").strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else None


def classification(room_type, district, capacity, price_cents, min_nights):
    """First failing rule is recorded once for a reconciled exclusion audit."""
    if room_type != "Entire home/apt":
        return "not_entire_home"
    if not district:
        return "missing_district"
    if capacity is None or not 1 <= capacity <= 6:
        return "capacity_outside_scope"
    if price_cents is None:
        return "missing_or_invalid_price"
    if not 3000 <= price_cents <= 50000:
        return "price_outside_scope"
    if min_nights is None or not 1 <= min_nights <= 30:
        return "min_nights_outside_scope"
    return "eligible"


def csv_export(connection, query, destination, header):
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(connection.execute(query))


def ensure_source(raw_path):
    if raw_path.exists():
        return
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "Berlin-Market-Portfolio/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_path.write_bytes(response.read())
    except Exception as exc:
        raise RuntimeError(
            "The official download failed. Download 'listings.csv.gz' from "
            "https://insideairbnb.com/get-the-data/ (Berlin, 19 Sep 2026), "
            f"save it as {raw_path}, and rerun. Original error: {exc}"
        ) from exc


def build(raw_path: Path, output_dir: Path):
    ensure_source(raw_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    database = output_dir / "market.sqlite"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE listing_audit (
                row_number INTEGER PRIMARY KEY,
                listing_id INTEGER,
                district TEXT,
                capacity INTEGER,
                price_cents INTEGER,
                minimum_nights INTEGER,
                review_count INTEGER,
                exclusion_reason TEXT NOT NULL
            );
            CREATE INDEX idx_audit_listing_id ON listing_audit (listing_id);
        """)
        rows = []
        with gzip.open(raw_path, "rt", newline="", encoding="utf-8-sig") if raw_path.suffix == ".gz" else raw_path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Source schema changed; missing columns: {sorted(missing)}")
            for row_number, entry in enumerate(reader, start=1):
                listing_id = parse_int(entry.get("id"))
                district = (entry.get("neighbourhood_group_cleansed") or "").strip()
                district = DISTRICT_NAMES.get(district, district)
                capacity = parse_int(entry.get("accommodates"))
                price_cents = parse_price(entry.get("price"))
                min_nights = parse_int(entry.get("minimum_nights"))
                reviews = parse_int(entry.get("number_of_reviews"))
                reason = classification(entry.get("room_type"), district, capacity,
                                        price_cents, min_nights)
                if listing_id is None or listing_id <= 0:
                    reason = "invalid_listing_id"
                rows.append((row_number, listing_id, district, capacity, price_cents,
                             min_nights, reviews, reason))
        if not rows:
            raise ValueError("The supplied source file contains no records")
        with connection:
            connection.executemany("INSERT INTO listing_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        duplicate_ids = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT listing_id FROM listing_audit
                WHERE listing_id IS NOT NULL
                GROUP BY listing_id HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        if duplicate_ids:
            raise ValueError(f"{duplicate_ids} duplicate listing IDs. Review source before importing.")
        connection.executescript("""
            CREATE TABLE dim_district (
                district_id INTEGER PRIMARY KEY,
                district TEXT NOT NULL UNIQUE
            );
            INSERT INTO dim_district (district_id, district)
            SELECT ROW_NUMBER() OVER (ORDER BY district), district
            FROM (SELECT DISTINCT district FROM listing_audit
                  WHERE exclusion_reason = 'eligible');

            CREATE TABLE dim_capacity (
                capacity INTEGER PRIMARY KEY,
                capacity_label TEXT NOT NULL
            );
            INSERT INTO dim_capacity VALUES
                (1, '1 guest'), (2, '2 guests'), (3, '3 guests'),
                (4, '4 guests'), (5, '5 guests'), (6, '6 guests');

            CREATE TABLE fact_listing (
                listing_id INTEGER PRIMARY KEY,
                district_id INTEGER NOT NULL REFERENCES dim_district(district_id),
                capacity INTEGER NOT NULL REFERENCES dim_capacity(capacity),
                asking_price_cents INTEGER NOT NULL,
                minimum_nights INTEGER NOT NULL,
                review_count INTEGER NOT NULL
            );
            INSERT INTO fact_listing
            SELECT a.listing_id, d.district_id, a.capacity, a.price_cents,
                   a.minimum_nights, COALESCE(a.review_count, 0)
            FROM listing_audit a
            JOIN dim_district d ON a.district = d.district
            WHERE a.exclusion_reason = 'eligible';
        """)
        checks = {
            "source_rows": len(rows),
            "eligible_rows": connection.execute("SELECT COUNT(*) FROM fact_listing").fetchone()[0],
            "excluded_rows": connection.execute("SELECT COUNT(*) FROM listing_audit WHERE exclusion_reason <> 'eligible'").fetchone()[0],
            "distinct_fact_ids": connection.execute("SELECT COUNT(DISTINCT listing_id) FROM fact_listing").fetchone()[0],
            "null_price_rows": connection.execute("SELECT COUNT(*) FROM fact_listing WHERE asking_price_cents IS NULL").fetchone()[0],
            "orphan_districts": connection.execute("SELECT COUNT(*) FROM fact_listing f LEFT JOIN dim_district d ON f.district_id = d.district_id WHERE d.district_id IS NULL").fetchone()[0],
            "orphan_capacities": connection.execute("SELECT COUNT(*) FROM fact_listing f LEFT JOIN dim_capacity c ON f.capacity = c.capacity WHERE c.capacity IS NULL").fetchone()[0],
            "districts": connection.execute("SELECT COUNT(*) FROM dim_district").fetchone()[0],
            "exclusions_by_reason": dict(connection.execute("SELECT exclusion_reason, COUNT(*) FROM listing_audit GROUP BY exclusion_reason ORDER BY exclusion_reason").fetchall()),
            "source_url": SOURCE,
            "source_sha256": file_sha256,
            "source_snapshot_date": SNAPSHOT,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "currency_assumption": "EUR (Inside Airbnb Berlin local currency; displayed $ is an export artifact)",
            "price_scope_eur": [30, 500],
            "min_nights_scope": [1, 30],
            "guest_capacity_scope": [1, 6]
        }
        assert checks["source_rows"] == checks["eligible_rows"] + checks["excluded_rows"]
        assert checks["eligible_rows"] == checks["distinct_fact_ids"]
        assert checks["orphan_districts"] == checks["orphan_capacities"] == checks["null_price_rows"] == 0
        assert checks["eligible_rows"] > 0, "No listings match the business scope"
        csv_export(connection, "SELECT listing_id, district_id, capacity, ROUND(asking_price_cents / 100.0, 2), minimum_nights, review_count FROM fact_listing ORDER BY listing_id", output_dir / "fact_listing.csv", ["ListingID", "DistrictID", "Capacity", "AskingPriceEUR", "MinimumNights", "ReviewCount"])
        csv_export(connection, "SELECT district_id, district FROM dim_district ORDER BY district_id", output_dir / "dim_district.csv", ["DistrictID", "District"])
        csv_export(connection, "SELECT capacity, capacity_label FROM dim_capacity ORDER BY capacity", output_dir / "dim_capacity.csv", ["Capacity", "CapacityLabel"])
        csv_export(connection, "SELECT exclusion_reason, COUNT(*) FROM listing_audit GROUP BY exclusion_reason ORDER BY exclusion_reason", output_dir / "exclusion_audit.csv", ["Reason", "Rows"])
        (output_dir / "quality_report.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"PASS | source={checks['source_rows']} eligible={checks['eligible_rows']} excluded={checks['excluded_rows']}")
        return checks
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/berlin_2026-09-19_listings.csv.gz"))
    parser.add_argument("--output", type=Path, default=Path("build"))
    args = parser.parse_args()
    build(args.input, args.output)


if __name__ == "__main__":
    main()
