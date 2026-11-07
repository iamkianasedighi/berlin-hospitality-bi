"""Small deterministic tests; fixture data is not an actual Berlin snapshot."""
import csv
from contextlib import closing
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from pipeline.build_market import build, classification, parse_price


class MarketBuildTests(unittest.TestCase):
    def test_price_parser(self):
        self.assertEqual(parse_price("$1,234.50"), 123450)
        self.assertEqual(parse_price("€86.00"), 8600)
        self.assertEqual(parse_price("95"), 9500)
        self.assertIsNone(parse_price("N/A"))

    def test_scope_reasons(self):
        self.assertEqual(classification("Private room", "Mitte", 2, 12000, 2), "not_entire_home")
        self.assertEqual(classification("Entire home/apt", "Mitte", 2, None, 2), "missing_or_invalid_price")
        self.assertEqual(classification("Entire home/apt", "Mitte", 2, 12000, 2), "eligible")

    def test_export_and_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "fixture.csv.gz"
            fields = ["id", "room_type", "neighbourhood_group_cleansed", "accommodates", "price", "minimum_nights", "number_of_reviews"]
            samples = [
                ("11", "Entire home/apt", "Mitte", "2", "$100.00", "2", "12"),
                ("12", "Entire home/apt", "Mitte", "4", "$140.00", "3", "0"),
                ("13", "Private room", "Mitte", "2", "$75.00", "1", "5"),
                ("14", "Entire home/apt", "Pankow", "2", "", "1", "3"),
                ("15", "Entire home/apt", "Pankow", "3", "$90.00", "31", "3"),
                ("16", "Entire home/apt", "Pankow", "2", "$80.00", "3", "4"),
            ]
            with gzip.open(raw, "wt", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                writer.writerows(samples)
            report = build(raw, root / "out")
            self.assertEqual((report["source_rows"], report["eligible_rows"], report["excluded_rows"]), (6, 3, 3))
            self.assertEqual(report["exclusions_by_reason"]["eligible"], 3)
            with closing(sqlite3.connect(root / "out" / "market.sqlite")) as db:
                self.assertEqual(db.execute("SELECT SUM(asking_price_cents) FROM fact_listing").fetchone()[0], 32000)
            with (root / "out" / "fact_listing.csv").open(encoding="utf-8") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 3)
            self.assertEqual(json.loads((root / "out" / "quality_report.json").read_text())["source_snapshot_date"], "2026-09-19")

    def test_duplicate_ids_fail(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "fixture.csv.gz"
            with gzip.open(p, "wt", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "room_type", "neighbourhood_group_cleansed", "accommodates", "price", "minimum_nights", "number_of_reviews"])
                writer.writerows([["1", "Entire home/apt", "Mitte", "2", "$90", "2", "0"]]*2)
            with self.assertRaisesRegex(ValueError, "duplicate listing IDs"):
                build(p, Path(td) / "out")


if __name__ == "__main__":
    unittest.main()
