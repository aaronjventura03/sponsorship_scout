"""Checks that the brand matching code behaves as intended.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v

Most tests use made-up properties and brands, so they keep passing when you
edit the CSVs. The last group checks the real sample data.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import matching
from data_loader import load_brands, load_category_fit, load_properties

BANDS = ["under18", "18_24", "25_34", "35_54", "55plus"]


def make_property(ages, property_type="player", minors=False):
    """A fake property. `ages` is five percentages that add up to 100."""
    prop = {"name": "Test property", "property_type": property_type, "audience_includes_minors": minors}
    for band, pct in zip(BANDS, ages):
        prop[f"age_{band}_pct"] = pct
    return prop


def make_brand(name, category, ages, minors_ok=True):
    """A fake brand. `ages` is five percentages that add up to 100."""
    brand = {
        "name": name,
        "category": category,
        "uk_link": "Test link",
        "suitable_for_minors": minors_ok,
    }
    for band, pct in zip(BANDS, ages):
        brand[f"target_age_{band}_pct"] = pct
    return brand


# A tiny fit table: category "a" suits players (10), category "b" does not (0).
FIT = [
    {"category": "a", "player": 10, "junior_event": 10},
    {"category": "b", "player": 0, "junior_event": 0},
]


class OverlapTests(unittest.TestCase):
    def test_identical_profiles_overlap_100(self):
        prop = make_property([10, 20, 30, 25, 15])
        brand = make_brand("X", "a", [10, 20, 30, 25, 15])
        self.assertEqual(matching.audience_overlap(prop, brand)[0], 100)

    def test_opposite_profiles_overlap_0(self):
        prop = make_property([100, 0, 0, 0, 0])
        brand = make_brand("X", "a", [0, 0, 0, 0, 100])
        self.assertEqual(matching.audience_overlap(prop, brand)[0], 0)

    def test_partial_overlap(self):
        prop = make_property([0, 50, 50, 0, 0])
        brand = make_brand("X", "a", [0, 0, 50, 50, 0])
        # Only the 25-34 band is shared, and both have 50% there.
        self.assertEqual(matching.audience_overlap(prop, brand)[0], 50)


class WeightTests(unittest.TestCase):
    def test_default_split_is_60_40(self):
        self.assertEqual(matching.MATCH_WEIGHTS, {"audience_overlap": 60, "category_fit": 40})

    def test_weights_are_rescaled_to_100(self):
        result = matching._normalise_weights({"audience_overlap": 3, "category_fit": 2})
        self.assertAlmostEqual(result["audience_overlap"], 60)
        self.assertAlmostEqual(result["category_fit"], 40)

    def test_perfect_brand_scores_100(self):
        prop = make_property([10, 20, 30, 25, 15])
        brand = make_brand("Perfect", "a", [10, 20, 30, 25, 15])
        result = matching.match_brands(prop, [brand], FIT)
        self.assertAlmostEqual(result["matches"][0]["total"], 100)

    def test_changing_the_split_can_change_the_winner(self):
        prop = make_property([0, 0, 100, 0, 0])
        great_audience = make_brand("Audience", "b", [0, 0, 100, 0, 0])  # overlap 100, fit 0
        great_category = make_brand("Category", "a", [100, 0, 0, 0, 0])  # overlap 0, fit 10
        by_default = matching.match_brands(prop, [great_audience, great_category], FIT)
        self.assertEqual(by_default["matches"][0]["brand"]["name"], "Audience")  # 60 beats 40
        category_heavy = {"audience_overlap": 20, "category_fit": 80}
        flipped = matching.match_brands(prop, [great_audience, great_category], FIT, weights=category_heavy)
        self.assertEqual(flipped["matches"][0]["brand"]["name"], "Category")


class SafetyRuleTests(unittest.TestCase):
    def test_unsuitable_brands_are_removed_for_youth_events(self):
        prop = make_property([50, 0, 0, 50, 0], property_type="junior_event", minors=True)
        safe = make_brand("Safe", "a", [50, 0, 0, 50, 0], minors_ok=True)
        unsafe = make_brand("Unsafe", "a", [50, 0, 0, 50, 0], minors_ok=False)
        result = matching.match_brands(prop, [safe, unsafe], FIT)
        names = [m["brand"]["name"] for m in result["matches"]]
        self.assertEqual(names, ["Safe"])
        self.assertEqual([e["brand"]["name"] for e in result["excluded"]], ["Unsafe"])

    def test_unsuitable_brands_stay_for_adult_events(self):
        prop = make_property([0, 0, 50, 50, 0], minors=False)
        unsafe = make_brand("Unsafe", "a", [0, 0, 50, 50, 0], minors_ok=False)
        result = matching.match_brands(prop, [unsafe], FIT)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["excluded"], [])


class RankingTests(unittest.TestCase):
    def test_returns_top_3_best_first(self):
        prop = make_property([0, 0, 100, 0, 0])
        brands = [
            make_brand("Best", "a", [0, 0, 100, 0, 0]),
            make_brand("Second", "a", [0, 0, 70, 30, 0]),
            make_brand("Third", "a", [0, 0, 40, 60, 0]),
            make_brand("Fourth", "a", [0, 0, 10, 90, 0]),
        ]
        names = [m["brand"]["name"] for m in matching.match_brands(prop, brands, FIT)["matches"]]
        self.assertEqual(names, ["Best", "Second", "Third"])

    def test_each_match_has_reasons(self):
        prop = make_property([0, 0, 100, 0, 0])
        result = matching.match_brands(prop, [make_brand("X", "a", [0, 0, 100, 0, 0])], FIT)
        reasons = result["matches"][0]["reasons"]
        self.assertEqual(len(reasons), 3)
        self.assertIn("Audience overlap", reasons[0])
        self.assertIn("Category fit", reasons[1])
        self.assertIn("UK link", reasons[2])

    def test_unknown_category_gives_a_clear_error(self):
        prop = make_property([0, 0, 100, 0, 0])
        with self.assertRaises(ValueError) as problem:
            matching.match_brands(prop, [make_brand("X", "mystery", [0, 0, 100, 0, 0])], FIT)
        self.assertIn("mystery", str(problem.exception))

    def test_unknown_property_type_gives_a_clear_error(self):
        prop = make_property([0, 0, 100, 0, 0], property_type="mystery_type")
        with self.assertRaises(ValueError) as problem:
            matching.match_brands(prop, [make_brand("X", "a", [0, 0, 100, 0, 0])], FIT)
        self.assertIn("mystery_type", str(problem.exception))


class TiebreakerTests(unittest.TestCase):
    def test_higher_audience_overlap_wins_a_tie(self):
        prop = make_property([0, 0, 100, 0, 0])
        # With a 50/50 split both brands score exactly 50:
        #   Low-fit brand:  overlap 80% -> 40 points, category fit 2/10 -> 10 points
        #   High-fit brand: overlap 40% -> 20 points, category fit 6/10 -> 30 points
        fit = [{"category": "two", "player": 2}, {"category": "six", "player": 6}]
        high_fit = make_brand("High fit", "six", [0, 0, 40, 60, 0])
        high_overlap = make_brand("High overlap", "two", [0, 0, 80, 20, 0])
        even_split = {"audience_overlap": 50, "category_fit": 50}
        # The high-fit brand is listed first, so without a tiebreaker it would win.
        result = matching.match_brands(prop, [high_fit, high_overlap], fit, weights=even_split)
        first, second = result["matches"]
        self.assertAlmostEqual(first["total"], second["total"])
        self.assertEqual(first["brand"]["name"], "High overlap")


class JointRankTests(unittest.TestCase):
    def setUp(self):
        self.prop = make_property([0, 0, 100, 0, 0])

    def test_identical_brands_share_a_joint_rank(self):
        twin_a = make_brand("Twin A", "a", [0, 0, 100, 0, 0])
        twin_b = make_brand("Twin B", "a", [0, 0, 100, 0, 0])
        result = matching.match_brands(self.prop, [twin_a, twin_b], FIT)
        self.assertEqual([m["rank_label"] for m in result["matches"]], ["=1", "=1"])

    def test_rank_after_a_joint_rank_is_skipped(self):
        brands = [
            make_brand("Best", "a", [0, 0, 100, 0, 0]),
            make_brand("Twin A", "a", [0, 0, 50, 50, 0]),
            make_brand("Twin B", "a", [0, 0, 50, 50, 0]),
            make_brand("Last", "a", [0, 0, 20, 80, 0]),
        ]
        result = matching.match_brands(self.prop, brands, FIT, top_n=4)
        labels = [(m["brand"]["name"], m["rank_label"]) for m in result["matches"]]
        self.assertEqual(labels, [("Best", "1"), ("Twin A", "=2"), ("Twin B", "=2"), ("Last", "4")])

    def test_brands_tied_for_the_last_place_are_all_included(self):
        brands = [
            make_brand("First", "a", [0, 0, 100, 0, 0]),
            make_brand("Second", "a", [0, 0, 70, 30, 0]),
            make_brand("Twin A", "a", [0, 0, 40, 60, 0]),
            make_brand("Twin B", "a", [0, 0, 40, 60, 0]),
        ]
        result = matching.match_brands(self.prop, brands, FIT)  # top 3 asked for
        self.assertEqual(
            [(m["brand"]["name"], m["rank_label"]) for m in result["matches"]],
            [("First", "1"), ("Second", "2"), ("Twin A", "=3"), ("Twin B", "=3")],
        )

    def test_file_order_does_not_decide_a_tie(self):
        twin_a = make_brand("Twin A", "a", [0, 0, 100, 0, 0])
        twin_b = make_brand("Twin B", "a", [0, 0, 100, 0, 0])
        forwards = matching.match_brands(self.prop, [twin_a, twin_b], FIT)["matches"]
        backwards = matching.match_brands(self.prop, [twin_b, twin_a], FIT)["matches"]
        self.assertEqual([m["rank"] for m in forwards], [m["rank"] for m in backwards])
        self.assertEqual({m["rank_label"] for m in forwards + backwards}, {"=1"})

    def test_joint_first_returns_the_brands_sharing_first_place(self):
        twin_a = make_brand("Twin A", "a", [0, 0, 100, 0, 0])
        twin_b = make_brand("Twin B", "a", [0, 0, 100, 0, 0])
        other = make_brand("Other", "a", [0, 0, 50, 50, 0])
        matches = matching.match_brands(self.prop, [twin_a, twin_b, other], FIT)["matches"]
        self.assertEqual({m["brand"]["name"] for m in matching.joint_first(matches)}, {"Twin A", "Twin B"})

    def test_joint_first_is_empty_when_there_is_a_clear_winner(self):
        best = make_brand("Best", "a", [0, 0, 100, 0, 0])
        other = make_brand("Other", "a", [0, 0, 50, 50, 0])
        matches = matching.match_brands(self.prop, [best, other], FIT)["matches"]
        self.assertEqual(matching.joint_first(matches), [])

    def test_a_tie_broken_by_overlap_is_not_a_joint_rank(self):
        # Same total score, different overlap: the overlap tiebreaker applies (see TiebreakerTests).
        fit = [{"category": "two", "player": 2}, {"category": "six", "player": 6}]
        even_split = {"audience_overlap": 50, "category_fit": 50}
        brands = [
            make_brand("High fit", "six", [0, 0, 40, 60, 0]),
            make_brand("High overlap", "two", [0, 0, 80, 20, 0]),
        ]
        result = matching.match_brands(self.prop, brands, fit, weights=even_split)
        self.assertEqual([m["rank_label"] for m in result["matches"]], ["1", "2"])


class FriendlyNameTests(unittest.TestCase):
    def test_reasons_use_the_category_label(self):
        prop = make_property([0, 0, 100, 0, 0])
        fit = [{"category": "a", "category_label": "luxury watch", "player": 10}]
        result = matching.match_brands(prop, [make_brand("X", "a", [0, 0, 100, 0, 0])], fit)
        self.assertIn("luxury watch brands suit", result["matches"][0]["reasons"][1])

    def test_missing_label_falls_back_to_the_category_name(self):
        prop = make_property([0, 0, 100, 0, 0])
        fit = [{"category": "food_drink", "player": 10}]
        result = matching.match_brands(prop, [make_brand("X", "food_drink", [0, 0, 100, 0, 0])], fit)
        self.assertIn("food drink brands suit", result["matches"][0]["reasons"][1])


class ReasonWordingTests(unittest.TestCase):
    def setUp(self):
        self.prop = make_property([0, 0, 100, 0, 0], property_type="premium_tournament")
        self.brand = make_brand("Wine", "drinks", [0, 0, 100, 0, 0])

    def reasons_for(self, fit):
        rows = [{"category": "drinks", "category_label": "premium drinks", "premium_tournament": fit}]
        return matching.match_brands(self.prop, [self.brand], rows)["matches"][0]["reasons"]

    def test_category_reason_reads_naturally(self):
        self.assertEqual(
            self.reasons_for(9)[1],
            "Category fit 9/10: premium drinks brands suit a premium tournament well.",
        )

    def test_the_fit_number_is_not_repeated(self):
        reason = self.reasons_for(9)[1]
        self.assertEqual(reason.count("9/10"), 1)
        self.assertNotIn("rated", reason)

    def test_wording_follows_the_fit_score(self):
        self.assertTrue(self.reasons_for(8)[1].endswith("suit a premium tournament well."))
        self.assertTrue(self.reasons_for(6)[1].endswith("reasonably well."))
        self.assertTrue(self.reasons_for(4)[1].endswith("only moderately well."))
        self.assertTrue(self.reasons_for(2)[1].endswith("poorly."))

    def test_article_matches_the_following_word(self):
        self.assertEqual(matching._with_article("player"), "a player")
        self.assertEqual(matching._with_article("university team"), "a university team")
        self.assertEqual(matching._with_article("elite event"), "an elite event")

    def test_removed_brand_messages_do_not_show_the_word_placeholder(self):
        youth_event = make_property([100, 0, 0, 0, 0], minors=True)
        wine = make_brand("Placeholder Wine", "drinks", [0, 0, 100, 0, 0], minors_ok=False)
        fit = [{"category": "drinks", "player": 5}]
        reason = matching.match_brands(youth_event, [wine], fit)["excluded"][0]["reason"]
        self.assertTrue(reason.startswith("Wine sells"))


class SampleDataTests(unittest.TestCase):
    def setUp(self):
        self.properties = load_properties()
        self.brands = load_brands()
        self.fit = load_category_fit()

    def test_every_property_gets_at_least_three_matches_ranked_within_the_top_three(self):
        # More than three come back only when brands share the last place.
        for prop in self.properties:
            matches = matching.match_brands(prop, self.brands, self.fit)["matches"]
            self.assertGreaterEqual(len(matches), 3, prop["name"])
            self.assertTrue(all(m["rank"] <= 3 for m in matches), prop["name"])

    def test_youth_event_never_gets_an_unsuitable_brand(self):
        for prop in self.properties:
            if prop["audience_includes_minors"]:
                result = matching.match_brands(prop, self.brands, self.fit)
                for match in result["matches"]:
                    self.assertTrue(match["brand"]["suitable_for_minors"], match["brand"]["name"])

    def test_only_age_restricted_brands_are_removed_for_youth_events(self):
        # The youth rule covers age-restricted products only (alcohol and similar).
        # Brands that merely do not target children, like a private bank, stay in.
        youth_event = next(p for p in self.properties if p["audience_includes_minors"])
        removed = {item["brand"]["category"] for item in matching.match_brands(youth_event, self.brands, self.fit)["excluded"]}
        self.assertEqual(removed, {"premium_drinks"})

    def test_every_brand_category_has_a_friendly_label(self):
        for row in self.fit:
            self.assertTrue(row.get("category_label"), f"{row['category']} has no category_label")

    def test_every_score_is_between_0_and_100(self):
        for prop in self.properties:
            for match in matching.match_brands(prop, self.brands, self.fit, top_n=99)["matches"]:
                self.assertTrue(0 <= match["total"] <= 100)


if __name__ == "__main__":
    unittest.main()
