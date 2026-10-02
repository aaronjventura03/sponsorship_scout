"""Checks that the four CSV files in data/ agree with each other.

Run these after editing any CSV. They catch the easy mistakes: age columns that
do not total 100, a brand category that is missing from category_fit.csv, and so on.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import load_activations, load_brands, load_category_fit, load_properties

BANDS = ["under18", "18_24", "25_34", "35_54", "55plus"]


class DataConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.properties = load_properties()
        self.brands = load_brands()
        self.fit = load_category_fit()
        self.activations = load_activations()

    def test_property_age_profiles_total_100(self):
        for prop in self.properties:
            self.assertEqual(sum(prop[f"age_{band}_pct"] for band in BANDS), 100, prop["id"])

    def test_brand_target_age_profiles_total_100(self):
        for brand in self.brands:
            self.assertEqual(sum(brand[f"target_age_{band}_pct"] for band in BANDS), 100, brand["id"])

    def test_ids_are_unique(self):
        for rows in (self.properties, self.brands):
            ids = [row["id"] for row in rows]
            self.assertEqual(len(ids), len(set(ids)))

    def test_brand_categories_match_category_fit_and_activations(self):
        fit_categories = {row["category"] for row in self.fit}
        self.assertEqual({b["category"] for b in self.brands} - fit_categories, set())
        self.assertEqual({a["category"] for a in self.activations} - fit_categories, set())
        self.assertEqual(fit_categories - {a["category"] for a in self.activations}, set())

    def test_every_category_has_at_least_two_activations(self):
        for row in self.fit:
            count = sum(1 for a in self.activations if a["category"] == row["category"])
            self.assertGreaterEqual(count, 2, row["category"])

    def test_every_property_type_has_a_category_fit_column(self):
        columns = set(self.fit[0])
        for prop in self.properties:
            self.assertIn(prop["property_type"], columns, prop["id"])

    def test_category_fit_scores_are_between_0_and_10(self):
        for row in self.fit:
            for column, value in row.items():
                if column not in ("category", "category_label"):
                    self.assertTrue(0 <= value <= 10, f"{row['category']} / {column} = {value}")

    def test_every_category_has_a_friendly_label(self):
        for row in self.fit:
            self.assertTrue(row.get("category_label"), row["category"])

    def test_values_are_in_sensible_ranges(self):
        for prop in self.properties:
            self.assertGreater(prop["annual_audience_reach"], 0, prop["id"])
            self.assertGreater(prop["annual_media_impressions"], 0, prop["id"])
            self.assertTrue(0 <= prop["engagement_rate_pct"] <= 100, prop["id"])
            self.assertTrue(0 <= prop["high_income_share_pct"] <= 100, prop["id"])
            self.assertTrue(1 <= prop["prestige_rating"] <= 10, prop["id"])

    def test_activations_are_written_to_the_brand_not_about_it(self):
        # The pitch is read by the brand, so ideas must not talk about "the brand".
        for row in self.activations:
            self.assertNotIn("the brand", row["activation"].lower(), row["activation"])


if __name__ == "__main__":
    unittest.main()
