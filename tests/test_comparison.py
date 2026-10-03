"""Checks the like-for-like comparison: every property's audience on the SAME measure.

No test here uses the internet: Wikipedia is replaced by stand-ins (see wiki_fixtures.py).

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import copy
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import comparison
import scoring
import wiki_fixtures as fixtures
import wikipedia_lookup as wiki
from data_loader import load_properties

TODAY = date(2026, 10, 3)


def views_for(title):
    """Page views as wikipedia_lookup returns them, from the stand-in Wikipedia."""
    return wiki.page_views(title, fixtures.make_fetch(), today=TODAY)


def prop(title="Queen's Club Championships", audience=1_848_000, **changes):
    """A property with five measured figures, linked to a Wikipedia page."""
    base = {
        "name": "Test", "property_type": "premium_tournament", "wikipedia_title": title,
        "annual_audience_reach": audience, "audience_source": "Attendance plus TV audience",
        "audience_source_url": "https://example.org", "audience_confidence": "published",
        "engagement_per_post": 500, "high_income_share_pct": 30, "broadcast_tier": 5, "prestige_rating": 5,
    }
    base.update(changes)
    return base


class LikeForLikeTests(unittest.TestCase):
    def test_the_audience_becomes_the_wikipedia_page_views_for_a_year(self):
        views = views_for("Toby Samuel")
        [converted] = comparison.like_for_like([prop("Toby Samuel", audience=6_369)], {"Toby Samuel": views})
        self.assertEqual(converted["annual_audience_reach"], 12_000)  # 1,000 a month x 12

    def test_it_is_labelled_as_calculated_page_views_with_a_source_link(self):
        views = views_for("Toby Samuel")
        [converted] = comparison.like_for_like([prop("Toby Samuel")], {"Toby Samuel": views})
        self.assertEqual(converted["audience_confidence"], "calculated")
        self.assertTrue(converted["audience_source"].startswith("Wikipedia page views"))
        self.assertTrue(converted["audience_source_url"].startswith("https://pageviews.wmcloud.org/"))

    def test_the_original_figure_is_kept_for_reference(self):
        views = views_for("Toby Samuel")
        [converted] = comparison.like_for_like([prop("Toby Samuel", audience=6_369)], {"Toby Samuel": views})
        self.assertEqual(converted["original_audience_reach"], 6_369)
        self.assertEqual(converted["original_audience_source"], "Attendance plus TV audience")
        self.assertIs(converted["like_for_like"], True)

    def test_the_input_properties_are_never_changed(self):
        original = [prop("Toby Samuel", audience=6_369)]
        snapshot = copy.deepcopy(original)
        comparison.like_for_like(original, {"Toby Samuel": views_for("Toby Samuel")})
        self.assertEqual(original, snapshot)

    def test_other_figures_are_untouched(self):
        views = views_for("Toby Samuel")
        source = prop("Toby Samuel")
        [converted] = comparison.like_for_like([source], {"Toby Samuel": views})
        for key in ("engagement_per_post", "high_income_share_pct", "broadcast_tier", "prestige_rating", "property_type", "name"):
            self.assertEqual(converted[key], source[key], key)

    def test_a_property_with_no_wikipedia_page_has_a_blank_audience(self):
        [converted] = comparison.like_for_like([prop(title="", audience=3_000)], {})
        self.assertEqual(converted["annual_audience_reach"], "")
        self.assertEqual(converted["audience_source"], comparison.NO_PAGE_SOURCE)
        self.assertEqual(converted["audience_confidence"], "")
        self.assertEqual(converted["original_audience_reach"], 3_000)

    def test_a_page_with_no_page_view_data_is_treated_the_same_way(self):
        [converted] = comparison.like_for_like([prop("Tiny Club")], {"Tiny Club": None})
        self.assertEqual(converted["annual_audience_reach"], "")

    def test_a_property_missing_the_title_column_altogether_is_handled(self):
        bare = prop()
        del bare["wikipedia_title"]
        [converted] = comparison.like_for_like([bare], {})
        self.assertEqual(converted["annual_audience_reach"], "")

    def test_order_and_count_are_preserved(self):
        props = [prop("A"), prop("B"), prop("C")]
        for index, item in enumerate(props):
            item["name"] = f"P{index}"
        converted = comparison.like_for_like(props, {})
        self.assertEqual([p["name"] for p in converted], ["P0", "P1", "P2"])


class FairnessTests(unittest.TestCase):
    """The whole point: on the same measure, the original audience figure no longer matters."""

    def score(self, properties, views):
        return [scoring.score_property(p)["total"] for p in comparison.like_for_like(properties, views)]

    def test_the_original_audience_figure_has_no_effect_in_this_mode(self):
        views = {"Toby Samuel": views_for("Toby Samuel")}
        small, huge = self.score([prop("Toby Samuel", audience=100), prop("Toby Samuel", audience=9_000_000)], views)
        self.assertEqual(small, huge)

    def test_the_same_figures_give_the_same_score_whatever_kind_of_audience_number_they_had(self):
        views = {"Toby Samuel": views_for("Toby Samuel"), "Queen's Club Championships": {**views_for("Toby Samuel")}}
        followers = prop("Toby Samuel", audience=6_369, audience_source="Instagram followers", property_type="player")
        attendance = prop("Queen's Club Championships", audience=1_848_000, property_type="player")
        first, second = self.score([followers, attendance], views)
        self.assertEqual(first, second)  # identical page views and identical other figures

    def test_more_page_views_means_a_higher_audience_score(self):
        views = {"Queen's Club Championships": views_for("Queen's Club Championships"), "Ilkley Trophy": views_for("Ilkley Trophy")}
        busy, quiet = comparison.like_for_like([prop("Queen's Club Championships"), prop("Ilkley Trophy")], views)
        self.assertGreater(
            scoring.factor_scores(busy)["audience"], scoring.factor_scores(quiet)["audience"]
        )

    def test_a_lookup_and_a_saved_property_are_compared_on_page_views_alone(self):
        # A saved property with a big real audience, and a lookup with only page views.
        saved = prop("Ilkley Trophy", audience=2_000_000)
        lookup = prop("Queen's Club Championships", audience=123_941, audience_source="Wikipedia page views: average of the last 12 complete months x 12 (a proxy)")
        views = {"Ilkley Trophy": views_for("Ilkley Trophy"), "Queen's Club Championships": views_for("Queen's Club Championships")}
        saved_total, lookup_total = self.score([saved, lookup], views)
        self.assertGreater(lookup_total, saved_total)  # 123,941 views beats 4,800, despite the saved 2 million

    def test_without_the_mode_the_comparison_would_have_been_unfair(self):
        saved = prop("Ilkley Trophy", audience=2_000_000)
        lookup = prop("Queen's Club Championships", audience=123_941)
        standard = [scoring.score_property(p)["total"] for p in (saved, lookup)]
        fair = self.score([saved, lookup], {"Ilkley Trophy": views_for("Ilkley Trophy"), "Queen's Club Championships": views_for("Queen's Club Championships")})
        self.assertGreater(standard[0], standard[1])  # standard: the 2 million wins
        self.assertLess(fair[0], fair[1])             # like for like: the busier page wins

    def test_a_property_with_no_page_is_scored_on_its_other_factors_with_the_weight_shared(self):
        [converted] = comparison.like_for_like([prop(title="")], {})
        result = scoring.score_property(converted)
        self.assertIn("audience", result["unmeasured"])
        self.assertEqual(result["factors"]["audience"]["weight"], 0)
        self.assertAlmostEqual(sum(f["weight"] for f in result["factors"].values()), 100)
        self.assertTrue(0 <= result["total"] <= 100)
        self.assertEqual(result["factors"]["audience"]["confidence"], "not measured")

    def test_the_standard_scores_are_untouched_by_all_this(self):
        props = load_properties()
        before = [scoring.score_property(p)["total"] for p in props]
        comparison.like_for_like(props, {"Queen's Club Championships": views_for("Queen's Club Championships")})
        self.assertEqual(before, [scoring.score_property(p)["total"] for p in props])


class EnsurePageViewsTests(unittest.TestCase):
    def ensure(self, cache, titles, calls=None, fetch=None):
        return comparison.ensure_page_views(cache, titles, fetch or fixtures.make_fetch(calls=calls), TODAY)

    def test_it_fetches_each_title_once_and_stores_the_result(self):
        calls, cache = [], {}
        problems = self.ensure(cache, ["Toby Samuel", "Queen's Club Championships"], calls)
        self.assertEqual(problems, [])
        self.assertEqual(set(cache), {"Toby Samuel", "Queen's Club Championships"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(cache["Toby Samuel"]["annual_estimate"], 12_000)

    def test_blank_titles_are_skipped_and_repeats_are_fetched_once(self):
        calls, cache = [], {}
        self.ensure(cache, ["", None, "Toby Samuel", "Toby Samuel", ""], calls)
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(cache), {"Toby Samuel"})

    def test_titles_already_in_the_cache_are_not_fetched_again(self):
        calls, cache = [], {}
        self.ensure(cache, ["Toby Samuel"], calls)
        self.ensure(cache, ["Toby Samuel"], calls)
        self.assertEqual(len(calls), 1)

    def test_only_the_missing_titles_are_fetched(self):
        calls, cache = [], {"Toby Samuel": views_for("Toby Samuel")}
        self.ensure(cache, ["Toby Samuel", "Ilkley Trophy"], calls)
        self.assertEqual(len(calls), 1)
        self.assertIn("Ilkley_Trophy", calls[0])

    def test_a_page_with_no_data_is_remembered_as_none_not_retried(self):
        calls, cache = [], {}
        self.ensure(cache, ["Tiny Club"], calls)
        self.assertEqual(cache, {"Tiny Club": None})
        self.ensure(cache, ["Tiny Club"], calls)
        self.assertEqual(len(calls), 1)

    def test_a_network_failure_is_reported_and_not_remembered(self):
        cache = {}
        down = mock.Mock(side_effect=wiki.WikipediaError("Could not reach Wikipedia."))
        problems = self.ensure(cache, ["Toby Samuel"], fetch=down)
        self.assertEqual(problems, ["Toby Samuel: Could not reach Wikipedia."])
        self.assertEqual(cache, {})  # so the next attempt tries again

    def test_a_failure_is_not_mistaken_for_no_page(self):
        cache = {}
        self.ensure(cache, ["Toby Samuel"], fetch=mock.Mock(side_effect=wiki.WikipediaError("down")))
        self.assertNotIn("Toby Samuel", cache)
        self.assertEqual(self.ensure(cache, ["Tiny Club"]), [])
        self.assertIn("Tiny Club", cache)  # genuinely no data: stored as None

    def test_one_failure_does_not_lose_the_others(self):
        real = fixtures.make_fetch()

        def flaky(url):
            if "Toby_Samuel" in url:
                raise wiki.WikipediaError("down")
            return real(url)

        cache = {}
        problems = self.ensure(cache, ["Toby Samuel", "Queen's Club Championships"], fetch=flaky)
        self.assertEqual(len(problems), 1)
        self.assertIn("Queen's Club Championships", cache)

    def test_it_recovers_once_wikipedia_is_back(self):
        cache = {}
        self.ensure(cache, ["Toby Samuel"], fetch=mock.Mock(side_effect=wiki.WikipediaError("down")))
        self.assertEqual(self.ensure(cache, ["Toby Samuel"]), [])
        self.assertEqual(cache["Toby Samuel"]["annual_estimate"], 12_000)

    def test_the_default_downloader_is_looked_up_when_called(self):
        with mock.patch.object(wiki, "fetch_json", fixtures.make_fetch()):
            cache = {}
            self.assertEqual(comparison.ensure_page_views(cache, ["Toby Samuel"], today=TODAY), [])
            self.assertIn("Toby Samuel", cache)


class SavedDataTests(unittest.TestCase):
    def test_every_title_in_the_saved_data_can_be_fetched_in_one_go(self):
        titles = [p["wikipedia_title"] for p in load_properties()]
        cache, calls = {}, []
        self.assertEqual(comparison.ensure_page_views(cache, titles, fixtures.make_fetch(calls=calls), TODAY), [])
        self.assertEqual(len(calls), 3)  # only three of the five saved properties have a Wikipedia page
        self.assertEqual(set(cache), {"Queen's Club Championships", "Ilkley Trophy", "Toby Samuel"})

    def test_the_two_without_a_page_are_not_measured_on_the_audience(self):
        props = load_properties()
        cache = {}
        comparison.ensure_page_views(cache, [p["wikipedia_title"] for p in props], fixtures.make_fetch(), TODAY)
        results = {p["id"]: scoring.score_property(p) for p in comparison.like_for_like(props, cache)}
        self.assertEqual(results["P03"]["unmeasured"], ["audience", "engagement"])  # no page, and no social account
        self.assertEqual(results["P04"]["unmeasured"], ["audience"])
        for property_id in ("P01", "P02", "P05"):
            self.assertNotIn("audience", results[property_id]["unmeasured"], property_id)

    def test_every_like_for_like_score_stays_out_of_100(self):
        props = load_properties()
        cache = {}
        comparison.ensure_page_views(cache, [p["wikipedia_title"] for p in props], fixtures.make_fetch(), TODAY)
        for converted in comparison.like_for_like(props, cache):
            self.assertTrue(0 <= scoring.score_property(converted)["total"] <= 100, converted["name"])


if __name__ == "__main__":
    unittest.main()
