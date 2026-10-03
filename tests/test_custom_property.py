"""Checks that a Wikipedia lookup plus the user's own entries becomes a proper property record,
and that the record works with the existing scoring, matching and pitch code.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import custom_property as cp
import scoring
import wiki_fixtures as fixtures
import wikipedia_lookup as wiki
from data_loader import load_activations, load_brands, load_category_fit, load_properties
from matching import match_brands
from pitch import generate_pitch

TYPES = ["premium_tournament", "challenger_tournament", "player", "university_team", "junior_event"]
TODAY = date(2026, 10, 3)


def lookup(title):
    return wiki.lookup_page(title, fixtures.make_fetch(), today=TODAY)


def filled_in(title="Queen's Club Championships", **changes):
    """The form's values for a page, with every figure filled in (as the user might)."""
    values = cp.default_values(lookup(title), TYPES)
    values["figures"]["engagement"] = {"value": 900, "mode": "sourced", "source": "Median of 10 posts", "url": ""}
    values["figures"]["demographics"] = {"value": 40.0, "mode": "estimated", "source": "", "url": ""}
    values["figures"]["media"] = {"value": 9, "mode": "estimated", "source": "", "url": ""}
    values["figures"]["prestige"] = {"value": 9, "mode": "estimated", "source": "", "url": ""}
    values.update(changes)
    return values


class DefaultValueTests(unittest.TestCase):
    def test_the_name_and_suggested_type_come_from_wikipedia(self):
        values = cp.default_values(lookup("Queen's Club Championships"), TYPES)
        self.assertEqual(values["name"], "Queen's Club Championships")
        self.assertEqual(values["property_type"], "premium_tournament")
        self.assertEqual(values["description"], "London tennis tournament")

    def test_page_views_fill_in_the_audience_as_a_sourced_figure(self):
        audience = cp.default_values(lookup("Toby Samuel"), TYPES)["figures"]["audience"]
        self.assertEqual(audience["value"], 12_000)  # average 1,000 a month x 12
        self.assertEqual(audience["mode"], "sourced")
        self.assertIn("last 12 complete months x 12", audience["source"])
        self.assertIn("proxy for public interest, not attendance", audience["source"])
        self.assertTrue(audience["url"].startswith("https://pageviews.wmcloud.org/"))

    def test_the_audience_can_be_left_blank_instead(self):
        audience = cp.default_values(lookup("Toby Samuel"), TYPES, use_pageviews=False)["figures"]["audience"]
        self.assertIsNone(audience["value"])
        self.assertEqual(audience["mode"], "estimated")

    def test_a_page_with_no_page_views_has_a_blank_audience(self):
        self.assertIsNone(cp.default_values(lookup("Tiny Club"), TYPES)["figures"]["audience"]["value"])

    def test_nothing_else_is_guessed(self):
        figures = cp.default_values(lookup("Queen's Club Championships"), TYPES)["figures"]
        for factor in ("engagement", "demographics", "media", "prestige"):
            self.assertEqual(figures[factor], {"value": None, "mode": "estimated", "source": "", "url": ""}, factor)

    def test_an_unclear_page_gets_no_suggested_type(self):
        values = cp.default_values(lookup("Tiny Club"), TYPES)
        self.assertIsNone(values["property_type"])

    def test_a_suggestion_outside_the_known_types_is_ignored(self):
        self.assertIsNone(cp.default_values(lookup("Toby Samuel"), ["premium_tournament"])["property_type"])

    def test_a_chosen_type_overrides_the_suggestion(self):
        values = cp.default_values(lookup("Queen's Club Championships"), TYPES, chosen_type="challenger_tournament")
        self.assertEqual(values["property_type"], "challenger_tournament")

    def test_youth_events_default_to_including_children(self):
        self.assertTrue(cp.default_values(lookup("Tiny Club"), TYPES, chosen_type="junior_event")["audience_includes_minors"])
        self.assertFalse(cp.default_values(lookup("Tiny Club"), TYPES, chosen_type="player")["audience_includes_minors"])

    def test_the_age_profile_starts_as_a_default_for_the_type(self):
        for kind in TYPES:
            values = cp.default_values(lookup("Tiny Club"), TYPES, chosen_type=kind)
            self.assertEqual(sum(values["age_profile"].values()), 100, kind)
        self.assertEqual(cp.default_values(lookup("Tiny Club"), TYPES, chosen_type="university_team")["age_profile"]["18_24"], 85)

    def test_the_default_age_profile_is_labelled_unresearched_and_estimated(self):
        values = cp.default_values(lookup("Tiny Club"), TYPES, chosen_type="player")
        self.assertEqual(values["age_mode"], "estimated")
        self.assertIn("not researched", values["age_source"])

    def test_the_default_profiles_match_the_ones_in_the_data(self):
        saved = {p["property_type"]: p for p in load_properties()}
        for kind in ("premium_tournament", "challenger_tournament", "player", "university_team", "junior_event"):
            expected = tuple(saved[kind][f"age_{part}_pct"] for part in ("under18", "18_24", "25_34", "35_54", "55plus"))
            self.assertEqual(cp.DEFAULT_AGE_PROFILES[kind], expected, kind)

    def test_the_figures_line_up_with_the_scoring_factors(self):
        self.assertEqual(set(cp.FIGURES), set(scoring.FACTOR_LABELS))
        for factor, spec in cp.FIGURES.items():
            self.assertEqual(spec["column"], scoring.INPUT_COLUMN[factor])
            self.assertEqual(f"{spec['prefix']}_confidence", scoring.CONFIDENCE_COLUMN[factor])


class BuildPropertyTests(unittest.TestCase):
    def test_a_complete_form_builds_a_property(self):
        prop, errors = cp.build_property(filled_in(), TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(prop["name"], "Queen's Club Championships")
        self.assertEqual(prop["property_type"], "premium_tournament")
        self.assertEqual(prop["annual_audience_reach"], round(sum(fixtures.CATALOGUE["Queen's Club Championships"]["views"]) / 12 * 12))
        self.assertEqual(prop["engagement_per_post"], 900)
        self.assertEqual(prop["high_income_share_pct"], 40.0)
        self.assertEqual(prop["broadcast_tier"], 9)
        self.assertEqual(prop["prestige_rating"], 9)
        self.assertEqual(prop["date_collected"], "2026-10-03")

    def test_it_is_marked_as_a_lookup_not_a_placeholder(self):
        prop, _ = cp.build_property(filled_in(), TODAY)
        self.assertIs(prop["from_wikipedia"], True)
        self.assertIs(prop["is_placeholder"], False)
        self.assertEqual(prop["id"], "LOOKUP-queen-s-club-championships")
        self.assertTrue(prop["wikipedia_url"].startswith("https://en.wikipedia.org/wiki/"))

    # --- sourced or estimated ---
    def test_sourced_and_estimated_figures_get_different_confidence_labels(self):
        prop, _ = cp.build_property(filled_in(), TODAY)
        self.assertEqual(prop["engagement_confidence"], "published")        # sourced, with a note
        self.assertEqual(prop["high_income_confidence"], "estimate")        # estimated
        self.assertEqual(prop["broadcast_confidence"], "estimate")

    def test_the_page_views_audience_is_calculated_not_published(self):
        prop, _ = cp.build_property(filled_in(), TODAY)
        self.assertEqual(prop["audience_confidence"], "calculated")
        self.assertIn("Wikipedia page views", prop["audience_source"])
        self.assertTrue(prop["audience_source_url"].startswith("https://pageviews.wmcloud.org/"))

    def test_an_audience_the_user_replaces_with_a_real_source_is_published(self):
        values = filled_in()
        values["figures"]["audience"] = {"value": 133_000, "mode": "sourced", "source": "LTA 2025 attendance", "url": "https://x.org"}
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(prop["audience_confidence"], "published")
        self.assertEqual(prop["audience_source"], "LTA 2025 attendance")
        self.assertEqual(prop["audience_source_url"], "https://x.org")

    def test_an_estimated_audience_is_labelled_estimate(self):
        values = filled_in()
        values["figures"]["audience"] = {"value": 50_000, "mode": "estimated", "source": "my guess", "url": ""}
        prop, _ = cp.build_property(values, TODAY)
        self.assertEqual(prop["audience_confidence"], "estimate")

    # --- sourced figures need a source ---
    def test_a_sourced_figure_without_a_source_note_is_rejected(self):
        values = filled_in()
        values["figures"]["prestige"] = {"value": 8, "mode": "sourced", "source": "   ", "url": ""}
        prop, errors = cp.build_property(values, TODAY)
        self.assertIsNone(prop)
        self.assertEqual(errors, ["Prestige (1 to 10): add a source, or mark it as Estimated."])

    def test_a_blank_figure_needs_no_source_even_if_marked_sourced(self):
        values = filled_in()
        values["figures"]["prestige"] = {"value": None, "mode": "sourced", "source": "", "url": ""}
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])

    def test_a_sourced_age_profile_needs_a_source_too(self):
        _, errors = cp.build_property(filled_in(age_mode="sourced", age_source=""), TODAY)
        self.assertIn("Audience age profile: add a source, or mark it as Estimated.", errors)

    # --- blank figures ---
    def test_blank_figures_are_stored_as_blank_not_zero(self):
        values = filled_in()
        for factor in ("engagement", "demographics", "media", "prestige"):
            values["figures"][factor] = {"value": None, "mode": "estimated", "source": "", "url": ""}
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])
        for column in ("engagement_per_post", "high_income_share_pct", "broadcast_tier", "prestige_rating"):
            self.assertEqual(prop[column], "", column)
        self.assertEqual(prop["engagement_confidence"], "not measurable")
        self.assertEqual(prop["high_income_confidence"], "")

    def test_blank_figures_have_no_source_columns_filled(self):
        values = filled_in()
        values["figures"]["prestige"] = {"value": None, "mode": "estimated", "source": "leftover note", "url": "https://x"}
        prop, _ = cp.build_property(values, TODAY)
        self.assertEqual((prop["prestige_source"], prop["prestige_source_url"]), ("", ""))

    # --- other checks ---
    def test_a_name_and_a_type_are_required(self):
        _, errors = cp.build_property(filled_in(name="  ", property_type=None), TODAY)
        self.assertIn("Give the property a name.", errors)
        self.assertIn("Choose a property type.", errors)

    def test_out_of_range_figures_are_rejected(self):
        values = filled_in()
        values["figures"]["prestige"]["value"] = 11
        values["figures"]["media"]["value"] = 12
        values["figures"]["demographics"]["value"] = 120.0
        values["figures"]["audience"]["value"] = -5
        values["figures"]["engagement"]["value"] = -1
        _, errors = cp.build_property(values, TODAY)
        text = " ".join(errors)
        for label in ("Prestige", "Broadcast tier", "higher-income", "Audience reach", "Engagements per post"):
            self.assertIn(label, text)

    def test_the_boundaries_are_allowed(self):
        values = filled_in()
        values["figures"]["prestige"]["value"] = 1
        values["figures"]["media"]["value"] = 0
        values["figures"]["demographics"]["value"] = 100.0
        _, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])

    def test_the_age_groups_must_total_100(self):
        values = filled_in()
        values["age_profile"]["35_54"] = 36  # the premium default is 8, 12, 20, 35, 25 = 100
        _, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, ["The audience age groups must total 100 (they total 101)."])

    def test_missing_age_groups_are_reported(self):
        values = filled_in()
        values["age_profile"]["under18"] = None
        _, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, ["Fill in all five audience age groups."])

    def test_an_engagement_rate_must_be_a_percentage(self):
        _, errors = cp.build_property(filled_in(engagement_rate_pct=150.0), TODAY)
        self.assertIn("Engagement rate: enter a percentage between 0 and 100.", errors)

    def test_every_problem_is_reported_at_once(self):
        values = filled_in(name="", property_type=None)
        values["figures"]["prestige"]["value"] = 11
        values["age_profile"]["35_54"] = 99
        _, errors = cp.build_property(values, TODAY)
        self.assertGreaterEqual(len(errors), 4)

    # --- the age profile record ---
    def test_the_age_profile_is_stored_in_the_data_columns_and_is_an_estimate(self):
        prop, _ = cp.build_property(filled_in(), TODAY)
        self.assertEqual([prop[f"age_{p}_pct"] for p in ("under18", "18_24", "25_34", "35_54", "55plus")], [8, 12, 20, 35, 25])
        self.assertEqual(prop["age_profile_confidence"], "estimate")
        self.assertIn("not researched", prop["age_profile_source"])

    def test_an_age_profile_the_user_changed_is_labelled_as_entered_by_them(self):
        values = filled_in()
        values["age_profile"].update({"35_54": 30, "55plus": 30})
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(prop["age_profile_source"], cp.ENTERED_AGE_SOURCE)
        self.assertEqual(prop["age_profile_confidence"], "estimate")  # still not sourced unless the user says so

    def test_the_youth_flag_is_kept(self):
        prop, _ = cp.build_property(filled_in(audience_includes_minors=True), TODAY)
        self.assertIs(prop["audience_includes_minors"], True)

    def test_whole_numbers_are_stored_as_whole_numbers(self):
        values = filled_in()
        values["figures"]["engagement"]["value"] = 900.0
        prop, _ = cp.build_property(values, TODAY)
        self.assertIsInstance(prop["engagement_per_post"], int)


class WorksWithTheRestOfTheAppTests(unittest.TestCase):
    """The record must flow through the existing scoring, matching and pitch unchanged."""

    def setUp(self):
        self.brands, self.fit, self.activations = load_brands(), load_category_fit(), load_activations()

    def build(self, **changes):
        prop, errors = cp.build_property(filled_in(**changes), TODAY)
        self.assertEqual(errors, [])
        return prop

    def test_it_has_every_column_the_saved_properties_have(self):
        saved = set(load_properties()[0])
        built = set(self.build())
        self.assertEqual(saved - built, set(), "the lookup record is missing columns that the saved properties have")

    def test_it_is_scored_out_of_100(self):
        result = scoring.score_property(self.build())
        self.assertTrue(0 < result["total"] <= 100)
        self.assertEqual(result["unmeasured"], [])

    def test_it_is_matched_to_brands(self):
        outcome = match_brands(self.build(), self.brands, self.fit)
        self.assertGreaterEqual(len(outcome["matches"]), 3)

    def test_it_gets_a_pitch(self):
        prop = self.build()
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        text = generate_pitch(prop, match, self.activations)
        self.assertIn("# Partnership opportunity: Queen's Club Championships ×", text)
        self.assertIn("Prepared by", text)

    def test_the_pitch_hedges_figures_the_user_marked_as_estimates(self):
        prop = self.build()
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        text = generate_pitch(prop, match, self.activations)
        self.assertIn("likely", text)  # the age profile is an estimate

    def test_estimated_audience_in_the_pitch_says_about(self):
        values = filled_in()
        values["figures"]["audience"] = {"value": 50_000, "mode": "estimated", "source": "", "url": ""}
        prop, _ = cp.build_property(values, TODAY)
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        self.assertIn("Audience reach: about 50,000 people", generate_pitch(prop, match, self.activations))

    def test_blank_figures_are_left_out_and_the_weights_are_redistributed(self):
        values = filled_in()
        for factor in ("engagement", "demographics", "media", "prestige"):
            values["figures"][factor] = {"value": None, "mode": "estimated", "source": "", "url": ""}
        prop, _ = cp.build_property(values, TODAY)
        result = scoring.score_property(prop)
        self.assertEqual(set(result["unmeasured"]), {"engagement", "demographics", "media", "prestige"})
        self.assertAlmostEqual(result["factors"]["audience"]["weight"], 100)  # the only measured factor
        self.assertTrue(0 <= result["total"] <= 100)

    def test_a_property_with_no_figures_at_all_still_works_end_to_end(self):
        values = filled_in()
        for factor in cp.FIGURES:
            values["figures"][factor] = {"value": None, "mode": "estimated", "source": "", "url": ""}
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(scoring.score_property(prop)["total"], 0)  # nothing measured, nothing to score
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        text = generate_pitch(prop, match, self.activations)  # must not crash on blank figures
        for bad in ("None", "nan", "{", "}"):
            self.assertNotIn(bad, text)

    def test_a_youth_event_lookup_gets_the_families_wording_and_the_youth_rule(self):
        prop = self.build(property_type="junior_event", audience_includes_minors=True)
        outcome = match_brands(prop, self.brands, self.fit)
        self.assertTrue(outcome["excluded"])  # age-restricted brands are removed
        text = generate_pitch(prop, outcome["matches"][0], self.activations)
        self.assertIn("The event reaches families: parents and young players together.", text)

    def test_a_player_with_a_page_views_audience_is_not_called_instagram_followers(self):
        prop, errors = cp.build_property(filled_in("Toby Samuel"), TODAY)
        self.assertEqual(errors, [])
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        text = generate_pitch(prop, match, self.activations)
        self.assertIn("Online interest: 12,000 Wikipedia page views a year", text)
        self.assertNotIn("Instagram followers", text)  # page views are not followers

    def test_a_player_whose_followers_the_user_entered_is_described_as_followers(self):
        values = filled_in("Toby Samuel")
        values["figures"]["audience"] = {"value": 6_369, "mode": "sourced", "source": "Instagram followers, 2 Oct 2026", "url": ""}
        prop, errors = cp.build_property(values, TODAY)
        self.assertEqual(errors, [])
        match = match_brands(prop, self.brands, self.fit)["matches"][0]
        self.assertIn("Instagram followers: 6,369", generate_pitch(prop, match, self.activations))

    def test_whole_percentages_are_stored_as_whole_numbers(self):
        prop, _ = cp.build_property(filled_in(), TODAY)  # the form gave 40.0
        self.assertEqual(prop["high_income_share_pct"], 40)
        self.assertIsInstance(prop["high_income_share_pct"], int)

    def test_fractional_percentages_are_kept(self):
        values = filled_in()
        values["figures"]["demographics"]["value"] = 37.5
        prop, _ = cp.build_property(values, TODAY)
        self.assertEqual(prop["high_income_share_pct"], 37.5)


if __name__ == "__main__":
    unittest.main()
