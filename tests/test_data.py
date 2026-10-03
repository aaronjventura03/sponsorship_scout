"""Checks that the four CSV files in data/ agree with each other.

Run these after editing any CSV. They catch the easy mistakes: age columns that
do not total 100, a brand category that is missing from category_fit.csv, and so on.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import load_activations, load_brands, load_category_fit, load_properties

BANDS = ["under18", "18_24", "25_34", "35_54", "55plus"]

# The five figures in properties.csv that each carry a source, a link and a confidence label.
FIGURES = ["audience", "engagement", "high_income", "broadcast", "prestige"]
CONFIDENCE_LABELS = {"published", "calculated", "estimate"}


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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
            self.assertTrue(0 <= prop["broadcast_tier"] <= 10, prop["id"])
            self.assertTrue(0 <= prop["high_income_share_pct"] <= 100, prop["id"])
            self.assertTrue(1 <= prop["prestige_rating"] <= 10, prop["id"])
            if is_number(prop["engagement_rate_pct"]):  # blank means "not measurable"
                self.assertTrue(0 <= prop["engagement_rate_pct"] <= 100, prop["id"])

    def test_the_old_media_impressions_column_is_gone(self):
        for prop in self.properties:
            self.assertNotIn("annual_media_impressions", prop)
            self.assertIn("broadcast_tier", prop)

    def test_every_figure_has_a_source_and_a_valid_confidence_label(self):
        for prop in self.properties:
            for figure in FIGURES:
                self.assertTrue(prop[f"{figure}_source"], f"{prop['id']} {figure}_source is empty")
                allowed = CONFIDENCE_LABELS
                if figure == "engagement" and not is_number(prop["engagement_per_post"]):
                    allowed = {"not measurable"}  # a figure that could not be measured says so
                self.assertIn(prop[f"{figure}_confidence"], allowed, f"{prop['id']} {figure}")
                self.assertIn(f"{figure}_source_url", prop)  # the column exists; the value may be blank
            self.assertTrue(prop["age_profile_source"], prop["id"])
            self.assertIn(prop["age_profile_confidence"], CONFIDENCE_LABELS, prop["id"])

    def test_every_property_has_a_valid_collection_date(self):
        for prop in self.properties:
            collected = date.fromisoformat(prop["date_collected"])  # raises if not YYYY-MM-DD
            self.assertLessEqual(collected, date.today(), prop["id"])

    def test_estimates_are_never_labelled_published(self):
        # Published figures should be whole, countable numbers taken from a source. Anything
        # recorded as an estimate in the source text must carry the estimate label.
        for prop in self.properties:
            for figure in FIGURES:
                if prop[f"{figure}_source"].lower().startswith("estimate"):
                    self.assertEqual(prop[f"{figure}_confidence"], "estimate", f"{prop['id']} {figure}")

    def test_engagement_figures_are_complete_or_clearly_not_measurable(self):
        for prop in self.properties:
            if is_number(prop["engagement_per_post"]):
                self.assertTrue(prop["engagement_account"], prop["id"])
                self.assertTrue(is_number(prop["engagement_followers"]), prop["id"])
                self.assertTrue(is_number(prop["engagement_rate_pct"]), prop["id"])
            else:
                # Not measurable: no rate and no follower count, and the source text says why.
                self.assertIn("not measurable", prop["engagement_source"].lower(), prop["id"])
                self.assertEqual(prop["engagement_rate_pct"], "", prop["id"])
                self.assertEqual(prop["engagement_followers"], "", prop["id"])

    def test_the_engagement_rate_is_the_median_divided_by_followers(self):
        # The rate is context only, but it must agree with the per-post figure it comes from.
        for prop in self.properties:
            if is_number(prop["engagement_per_post"]):
                worked_out = prop["engagement_per_post"] / prop["engagement_followers"] * 100
                self.assertAlmostEqual(worked_out, prop["engagement_rate_pct"], delta=0.06, msg=prop["id"])

    def test_real_properties_are_not_marked_as_placeholders(self):
        for prop in self.properties:
            self.assertIs(prop["is_placeholder"], False, prop["id"])

    def test_brands_are_still_illustrative_placeholders(self):
        for brand in self.brands:
            self.assertIs(brand["is_placeholder"], True, brand["id"])

    def test_an_audience_age_profile_is_recorded_as_an_estimate_until_researched(self):
        # The age profiles were carried over from the version 1 sample data.
        for prop in self.properties:
            self.assertEqual(prop["age_profile_confidence"], "estimate", prop["id"])

    def test_activations_are_written_to_the_brand_not_about_it(self):
        # The pitch is read by the brand, so ideas must not talk about "the brand".
        for row in self.activations:
            self.assertNotIn("the brand", row["activation"].lower(), row["activation"])


class RealDataTests(unittest.TestCase):
    """Pins the exact figures collected on 2 October 2026, so a typo in the CSV is caught.
    When you refresh the data with new research, update the table below to match."""

    # id: (name, type, audience, engagements per post, engagement %, followers behind it,
    #      high-income %, broadcast tier, prestige, includes minors)
    EXPECTED = {
        "P01": ("Queen's (HSBC Championships)", "premium_tournament", 1_848_000, 2_025, 2.9, 70_100, 35, 9, 9, False),
        "P02": ("Lexus Ilkley Open", "challenger_tournament", 20_000, 89, 1.8, 4_816, 40, 4, 5, False),
        "P03": ("Lexus British Open Roehampton (ITF J300)", "junior_event", 3_000, "", "", "", 40, 2, 4, True),
        "P04": ("Queen Mary Tennis Club (BUCS)", "university_team", 150, 23, 2.2, 1_036, 10, 0, 2, False),
        "P05": ("Toby Samuel", "player", 6_369, 878, 13.8, 6_369, 30, 5, 5, False),
    }

    def test_the_five_properties_hold_the_researched_figures(self):
        properties = {p["id"]: p for p in load_properties()}
        self.assertEqual(set(properties), set(self.EXPECTED))
        for prop_id, (name, kind, audience, per_post, rate, followers, income, tier, prestige, minors) in self.EXPECTED.items():
            prop = properties[prop_id]
            self.assertEqual(
                (prop["name"], prop["property_type"], prop["annual_audience_reach"], prop["engagement_per_post"],
                 prop["engagement_rate_pct"], prop["engagement_followers"], prop["high_income_share_pct"],
                 prop["broadcast_tier"], prop["prestige_rating"], prop["audience_includes_minors"]),
                (name, kind, audience, per_post, rate, followers, income, tier, prestige, minors),
                prop_id,
            )
            self.assertEqual(prop["date_collected"], "2026-10-02", prop_id)

    def test_source_links_are_recorded_where_given_and_left_blank_otherwise(self):
        by_id = {p["id"]: p for p in load_properties()}
        self.assertEqual(
            by_id["P02"]["audience_source_url"],
            "https://www.lta.org.uk/49c743/siteassets/events/ilkley/media/2025-lexus-ilkley-open-programme.pdf",
        )
        self.assertEqual(
            by_id["P03"]["audience_source_url"],
            "https://www.itftennis.com/en/tournament/j300-roehampton/gbr/2026/j-j300-gbr-2026-001/",
        )
        # Queen's is cited as "LTA, 2025" with no link for now. No link was invented.
        self.assertTrue(by_id["P01"]["audience_source"].startswith("LTA, 2025"))
        self.assertEqual(by_id["P01"]["audience_source_url"], "")
        for prop in by_id.values():
            for figure in FIGURES:
                url = prop[f"{figure}_source_url"]
                self.assertTrue(url == "" or url.startswith("https://"), f"{prop['id']} {figure}: {url}")

    def test_the_ilkley_description_is_the_agreed_one(self):
        by_id = {p["id"]: p for p in load_properties()}
        self.assertEqual(by_id["P02"]["description"], "ATP Challenger 125 and WTA 125 grass-court event in Ilkley, West Yorkshire")
        self.assertEqual(by_id["P05"]["description"], "Professional player ranked 100 in the ATP rankings on 2 October 2026")

    def test_age_profiles_follow_the_judgement_for_the_two_adjusted_properties(self):
        by_id = {p["id"]: p for p in load_properties()}
        queen_mary = by_id["P04"]
        bands = {b: queen_mary[f"age_{b}_pct"] for b in BANDS}
        self.assertEqual(max(bands, key=bands.get), "18_24")
        self.assertGreaterEqual(bands["18_24"], 80)  # mostly 18-24
        roehampton = by_id["P03"]
        bands = {b: roehampton[f"age_{b}_pct"] for b in BANDS}
        top_two = sorted(bands, key=bands.get, reverse=True)[:2]
        self.assertEqual(set(top_two), {"under18", "35_54"})  # young players and their parents
        self.assertGreaterEqual(bands["under18"] + bands["35_54"], 85)
        for prop in by_id.values():  # still flagged as unresearched estimates
            self.assertEqual(prop["age_profile_confidence"], "estimate", prop["id"])
            self.assertIn("not researched", prop["age_profile_source"], prop["id"])

    def test_confidence_labels_match_how_each_figure_was_obtained(self):
        by_id = {p["id"]: p for p in load_properties()}
        self.assertEqual(by_id["P01"]["audience_confidence"], "calculated")  # a sum of two published figures
        self.assertEqual(by_id["P02"]["audience_confidence"], "published")   # attendance from the programme
        self.assertEqual(by_id["P03"]["audience_confidence"], "estimate")    # low confidence, no published figure
        self.assertEqual(by_id["P04"]["audience_confidence"], "estimate")
        self.assertEqual(by_id["P05"]["audience_confidence"], "published")   # Instagram followers
        for prop_id in ("P01", "P02", "P04", "P05"):
            self.assertEqual(by_id[prop_id]["engagement_confidence"], "calculated", prop_id)  # a median
        self.assertEqual(by_id["P03"]["engagement_confidence"], "not measurable")
        for prop in by_id.values():
            self.assertEqual(prop["high_income_confidence"], "estimate", prop["id"])

    def test_each_saved_property_records_its_wikipedia_page(self):
        titles = {p["id"]: p["wikipedia_title"] for p in load_properties()}
        self.assertEqual(titles, {
            "P01": "Queen's Club Championships",
            "P02": "Ilkley Trophy",  # the Lexus Ilkley Open's page; "Ilkley Open" is a different, historic event
            "P03": "",               # no Wikipedia page (checked 3 October 2026)
            "P04": "",               # no Wikipedia page (checked 3 October 2026)
            "P05": "Toby Samuel",
        })

    def test_wikipedia_titles_are_clean_and_unique(self):
        filled = [p["wikipedia_title"] for p in load_properties() if p["wikipedia_title"]]
        self.assertEqual(len(filled), len(set(filled)))
        for title in filled:
            self.assertEqual(title, title.strip())
            self.assertNotIn("_", title)       # a title with spaces, as Wikipedia writes it
            self.assertNotIn("wikipedia.org", title)  # a title, not a web address

    def test_financial_services_fits_a_premium_tournament_at_9(self):
        rows = {row["category"]: row for row in load_category_fit()}
        self.assertEqual(rows["financial_services"]["premium_tournament"], 9)


if __name__ == "__main__":
    unittest.main()
