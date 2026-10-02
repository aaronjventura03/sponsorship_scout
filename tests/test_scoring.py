"""Checks that the scoring code behaves as intended.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v

These tests use made-up properties (not your CSV), so they keep passing
when you edit the sample data.
"""

import sys
import unittest
from pathlib import Path

# Let the tests find scoring.py and data_loader.py one folder up.
sys.path.insert(0, str(Path(__file__).parent.parent))

import scoring
from data_loader import load_properties


def make_property(audience, engagement, income, media, prestige):
    """Build a fake property with just the fields scoring needs."""
    return {
        "annual_audience_reach": audience,
        "engagement_rate_pct": engagement,
        "high_income_share_pct": income,
        "annual_media_impressions": media,
        "prestige_rating": prestige,
    }


# A property that hits the top of every scale, and one that hits the bottom.
BEST = make_property(
    scoring.AUDIENCE_CEILING,
    scoring.ENGAGEMENT_CEILING_PCT,
    scoring.HIGH_INCOME_CEILING_PCT,
    scoring.MEDIA_CEILING,
    10,
)
WORST = make_property(1, 0, 0, 1, 0)


class ScaleTests(unittest.TestCase):
    def test_log_scale_ends(self):
        self.assertEqual(scoring.log_scale(1_000, 1_000, 1_000_000), 0)
        self.assertAlmostEqual(scoring.log_scale(1_000_000, 1_000, 1_000_000), 10)

    def test_log_scale_is_capped(self):
        self.assertEqual(scoring.log_scale(5, 1_000, 1_000_000), 0)
        self.assertEqual(scoring.log_scale(9_999_999_999, 1_000, 1_000_000), 10)

    def test_log_scale_middle(self):
        # 31,623 is the halfway point between 1,000 and 1,000,000 on a log scale.
        self.assertAlmostEqual(scoring.log_scale(31_623, 1_000, 1_000_000), 5, places=2)

    def test_log_scale_lets_small_properties_score(self):
        # A 10x smaller audience loses a fixed number of points, not 90%.
        big = scoring.log_scale(2_000_000, 1_000, 20_000_000)
        small = scoring.log_scale(200_000, 1_000, 20_000_000)
        self.assertGreater(small, big / 2)

    def test_straight_line_scale(self):
        self.assertEqual(scoring.straight_line_scale(0, 8), 0)
        self.assertEqual(scoring.straight_line_scale(4, 8), 5)
        self.assertEqual(scoring.straight_line_scale(8, 8), 10)
        self.assertEqual(scoring.straight_line_scale(20, 8), 10)  # capped


class WeightTests(unittest.TestCase):
    def test_default_weights_total_100(self):
        self.assertEqual(sum(scoring.DEFAULT_WEIGHTS.values()), 100)

    def test_default_weights_match_the_plan(self):
        self.assertEqual(
            scoring.DEFAULT_WEIGHTS,
            {"audience": 25, "engagement": 20, "demographics": 20, "media": 20, "prestige": 15},
        )

    def test_normalise_totals_100_and_keeps_proportions(self):
        result = scoring.normalise_weights({"a": 50, "b": 50, "c": 100})
        self.assertAlmostEqual(sum(result.values()), 100)
        self.assertAlmostEqual(result["a"], 25)
        self.assertAlmostEqual(result["c"], 50)

    def test_normalise_rejects_all_zero(self):
        with self.assertRaises(ValueError):
            scoring.normalise_weights({"a": 0, "b": 0})


class ScoreTests(unittest.TestCase):
    def test_best_property_scores_100(self):
        self.assertAlmostEqual(scoring.score_property(BEST)["total"], 100)

    def test_worst_property_scores_0(self):
        self.assertAlmostEqual(scoring.score_property(WORST)["total"], 0)

    def test_breakdown_adds_up_to_total(self):
        result = scoring.score_property(make_property(500_000, 4, 30, 5_000_000, 6))
        points = sum(item["points"] for item in result["factors"].values())
        self.assertAlmostEqual(points, result["total"])

    def test_changing_weights_changes_score_but_stays_out_of_100(self):
        prop = make_property(500_000, 8, 10, 1_000_000, 3)
        engagement_heavy = {"audience": 1, "engagement": 90, "demographics": 3, "media": 3, "prestige": 3}
        default_total = scoring.score_property(prop)["total"]
        heavy_total = scoring.score_property(prop, engagement_heavy)["total"]
        self.assertGreater(heavy_total, default_total)  # engagement is this property's strength
        self.assertLessEqual(heavy_total, 100)
        weights_used = [item["weight"] for item in scoring.score_property(prop, engagement_heavy)["factors"].values()]
        self.assertAlmostEqual(sum(weights_used), 100)

    def test_ranking_is_best_first(self):
        small = make_property(10_000, 2, 10, 200_000, 2)
        medium = make_property(500_000, 4, 25, 5_000_000, 5)
        large = make_property(10_000_000, 4, 40, 200_000_000, 9)
        ranked = scoring.rank_properties([small, large, medium])
        self.assertEqual([pair[0] for pair in ranked], [large, medium, small])

    def test_age_does_not_affect_the_score(self):
        # Age lives in brand matching, not here.
        young = {**make_property(500_000, 4, 30, 5_000_000, 6), "age_18_24_pct": 90}
        older = {**make_property(500_000, 4, 30, 5_000_000, 6), "age_55plus_pct": 90}
        self.assertEqual(scoring.score_property(young)["total"], scoring.score_property(older)["total"])


class RankLabelTests(unittest.TestCase):
    def test_no_ties(self):
        self.assertEqual(scoring.rank_labels([90, 80, 70]), ["1", "2", "3"])

    def test_tied_scores_share_a_rank_and_the_next_is_skipped(self):
        self.assertEqual(scoring.rank_labels([90, 80, 70, 70, 50]), ["1", "2", "=3", "=3", "5"])

    def test_tiny_computer_rounding_differences_still_count_as_a_tie(self):
        self.assertEqual(scoring.rank_labels([80.0000000001, 80.0]), ["=1", "=1"])

    def test_empty_list(self):
        self.assertEqual(scoring.rank_labels([]), [])


class SampleDataTests(unittest.TestCase):
    def test_every_sample_property_scores_between_0_and_100(self):
        for prop in load_properties():
            total = scoring.score_property(prop)["total"]
            self.assertTrue(0 <= total <= 100, f"{prop['name']} scored {total}")


if __name__ == "__main__":
    unittest.main()
