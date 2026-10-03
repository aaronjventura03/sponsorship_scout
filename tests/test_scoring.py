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


def make_property(audience, engagement, income, broadcast_tier, prestige, **extra):
    """Build a fake property with just the fields scoring needs."""
    prop = {
        "annual_audience_reach": audience,
        "engagement_per_post": engagement,  # median engagements (likes + comments) per post
        "high_income_share_pct": income,
        "broadcast_tier": broadcast_tier,
        "prestige_rating": prestige,
    }
    prop.update(extra)
    return prop


# A property that hits the top of every scale, and one that hits the bottom.
BEST = make_property(
    scoring.AUDIENCE_CEILING,
    scoring.ENGAGEMENT_CEILING,
    scoring.HIGH_INCOME_CEILING_PCT,
    10,
    10,
)
WORST = make_property(1, 0, 0, 0, 0)


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
        result = scoring.score_property(make_property(500_000, 4, 30, 5, 6))
        points = sum(item["points"] for item in result["factors"].values())
        self.assertAlmostEqual(points, result["total"])

    def test_changing_weights_changes_score_but_stays_out_of_100(self):
        prop = make_property(500_000, 5_000, 10, 3, 3)
        engagement_heavy = {"audience": 1, "engagement": 90, "demographics": 3, "media": 3, "prestige": 3}
        default_total = scoring.score_property(prop)["total"]
        heavy_total = scoring.score_property(prop, engagement_heavy)["total"]
        self.assertGreater(heavy_total, default_total)  # engagement is this property's strength
        self.assertLessEqual(heavy_total, 100)
        weights_used = [item["weight"] for item in scoring.score_property(prop, engagement_heavy)["factors"].values()]
        self.assertAlmostEqual(sum(weights_used), 100)

    def test_ranking_is_best_first(self):
        small = make_property(10_000, 20, 10, 1, 2)
        medium = make_property(500_000, 200, 25, 5, 5)
        large = make_property(10_000_000, 2_000, 40, 9, 9)
        ranked = scoring.rank_properties([small, large, medium])
        self.assertEqual([pair[0] for pair in ranked], [large, medium, small])

    def test_age_does_not_affect_the_score(self):
        # Age lives in brand matching, not here.
        young = {**make_property(500_000, 4, 30, 5, 6), "age_18_24_pct": 90}
        older = {**make_property(500_000, 4, 30, 5, 6), "age_55plus_pct": 90}
        self.assertEqual(scoring.score_property(young)["total"], scoring.score_property(older)["total"])


class BroadcastTests(unittest.TestCase):
    def test_the_broadcast_tier_is_used_directly_as_the_score(self):
        for tier in (0, 2, 5, 9, 10):
            self.assertEqual(scoring.factor_scores(make_property(1000, 4, 30, tier, 5))["media"], tier)

    def test_rubric_descriptions_follow_the_tiers(self):
        self.assertEqual(scoring.broadcast_description(10), "live free-to-air television")
        self.assertEqual(scoring.broadcast_description(9), "live free-to-air television")
        self.assertEqual(scoring.broadcast_description(8), "live television and streaming")
        self.assertEqual(scoring.broadcast_description(5), "live streaming")
        self.assertEqual(scoring.broadcast_description(4), "live streaming")
        self.assertEqual(scoring.broadcast_description(2), "limited streaming or highlights")
        self.assertEqual(scoring.broadcast_description(1), "social media video only")
        self.assertEqual(scoring.broadcast_description(0), "no broadcast or streaming coverage")

    def test_free_to_air_rates_above_streaming_above_nothing(self):
        free_to_air = scoring.broadcast_description(9)
        streaming = scoring.broadcast_description(5)
        self.assertIn("free-to-air", free_to_air)
        self.assertIn("streaming", streaming)
        self.assertNotIn("free-to-air", streaming)

    def test_rubric_covers_every_tier_from_0_to_10(self):
        for tier in range(11):
            self.assertTrue(scoring.broadcast_description(tier))


class EngagementScaleTests(unittest.TestCase):
    """Engagement is scored as engagements per post on a log scale, not as a rate."""

    def score(self, per_post, **extra):
        return scoring.factor_scores(make_property(1000, per_post, 30, 5, 5, **extra))["engagement"]

    def test_the_bounds_are_10_and_10000(self):
        self.assertEqual(scoring.ENGAGEMENT_FLOOR, 10)
        self.assertEqual(scoring.ENGAGEMENT_CEILING, 10_000)

    def test_ends_of_the_scale(self):
        self.assertEqual(self.score(10), 0)
        self.assertAlmostEqual(self.score(10_000), 10)
        self.assertEqual(self.score(50_000), 10)  # capped

    def test_real_values_are_spread_across_the_scale_in_order(self):
        # The real medians: Queen Mary 23, Ilkley 89, Toby Samuel 878, Queen's 2,025.
        scores = [self.score(value) for value in (23, 89, 878, 2_025)]
        self.assertEqual(scores, sorted(scores))
        self.assertTrue(all(b - a > 1 for a, b in zip(scores, scores[1:])), scores)
        self.assertAlmostEqual(scores[0], 1.2, places=1)
        self.assertAlmostEqual(scores[3], 7.7, places=1)

    def test_a_big_account_beats_a_small_one_even_when_the_small_ones_rate_is_higher(self):
        # Queen's: 2,025 per post but a 2.9% rate. Toby Samuel: 878 per post but a 13.8% rate.
        queens = self.score(2_025, engagement_rate_pct=2.9, engagement_followers=70_100)
        toby = self.score(878, engagement_rate_pct=13.8, engagement_followers=6_369)
        self.assertGreater(queens, toby)

    def test_the_rate_does_not_change_the_score(self):
        low_rate = self.score(878, engagement_rate_pct=0.1)
        high_rate = self.score(878, engagement_rate_pct=99)
        self.assertEqual(low_rate, high_rate)


class EngagementMeasurableTests(unittest.TestCase):
    def measurable(self, per_post, followers):
        prop = make_property(1000, per_post, 30, 5, 5, engagement_followers=followers)
        return scoring.engagement_is_measurable(prop)

    def test_a_normal_account_is_measurable(self):
        self.assertTrue(self.measurable(878, 6_369))

    def test_a_blank_figure_is_not_measurable(self):
        self.assertFalse(self.measurable("", ""))

    def test_an_account_under_1000_followers_is_not_measurable(self):
        self.assertFalse(self.measurable(500, 999))

    def test_exactly_1000_followers_is_trusted(self):
        self.assertTrue(self.measurable(500, 1_000))
        self.assertEqual(scoring.ENGAGEMENT_MIN_FOLLOWERS, 1_000)

    def test_zero_engagements_on_a_big_account_is_measured_not_missing(self):
        self.assertTrue(self.measurable(0, 5_000))

    def test_a_missing_follower_count_is_not_held_against_the_property(self):
        self.assertTrue(scoring.engagement_is_measurable(make_property(1000, 400, 30, 5, 5)))

    def test_there_is_no_neutral_score_any_more(self):
        self.assertFalse(hasattr(scoring, "ENGAGEMENT_NEUTRAL_SCORE"))
        unmeasured = scoring.factor_scores(make_property(1000, "", 30, 5, 5))
        self.assertIsNone(unmeasured["engagement"])  # left out, not given a middle score


class RedistributionTests(unittest.TestCase):
    """A factor that cannot be measured is left out and its weight shared across the rest."""

    def unmeasured_engagement(self, **extra):
        return make_property(100_000, "", 30, 5, 5, **extra)

    def test_the_unmeasured_weight_is_shared_in_proportion(self):
        factors = scoring.score_property(self.unmeasured_engagement())["factors"]
        # Default weights 25/20/20/20/15 with engagement (20) removed: the other 80 scale up by 100/80.
        self.assertAlmostEqual(factors["audience"]["weight"], 25 * 100 / 80)
        self.assertAlmostEqual(factors["demographics"]["weight"], 20 * 100 / 80)
        self.assertAlmostEqual(factors["media"]["weight"], 20 * 100 / 80)
        self.assertAlmostEqual(factors["prestige"]["weight"], 15 * 100 / 80)
        self.assertEqual(factors["engagement"]["weight"], 0)

    def test_the_weights_used_still_total_100(self):
        factors = scoring.score_property(self.unmeasured_engagement())["factors"]
        self.assertAlmostEqual(sum(item["weight"] for item in factors.values()), 100)

    def test_the_weight_you_set_is_still_reported(self):
        factors = scoring.score_property(self.unmeasured_engagement())["factors"]
        self.assertEqual(factors["engagement"]["set_weight"], 20)
        self.assertEqual(factors["audience"]["set_weight"], 25)

    def test_an_unmeasured_factor_has_no_score_no_points_and_is_labelled(self):
        item = scoring.score_property(self.unmeasured_engagement())["factors"]["engagement"]
        self.assertIsNone(item["score"])
        self.assertEqual(item["points"], 0)
        self.assertFalse(item["measured"])
        self.assertEqual(item["confidence"], "not measured")

    def test_the_result_lists_what_was_left_out(self):
        self.assertEqual(scoring.score_property(self.unmeasured_engagement())["unmeasured"], ["engagement"])
        self.assertEqual(scoring.score_property(make_property(1000, 500, 30, 5, 5))["unmeasured"], [])

    def test_the_score_uses_only_measured_evidence_and_is_still_out_of_100(self):
        perfect_except_engagement = make_property(scoring.AUDIENCE_CEILING, "", scoring.HIGH_INCOME_CEILING_PCT, 10, 10)
        self.assertAlmostEqual(scoring.score_property(perfect_except_engagement)["total"], 100)

    def test_it_equals_scoring_with_that_factors_weight_set_to_zero(self):
        prop = self.unmeasured_engagement()
        without_engagement = {"audience": 25, "engagement": 0, "demographics": 20, "media": 20, "prestige": 15}
        self.assertAlmostEqual(scoring.score_property(prop)["total"], scoring.score_property(prop, without_engagement)["total"])

    def test_breakdown_points_add_up_to_the_total(self):
        result = scoring.score_property(self.unmeasured_engagement())
        self.assertAlmostEqual(sum(item["points"] for item in result["factors"].values()), result["total"])

    def test_it_respects_changed_slider_weights(self):
        weights = {"audience": 60, "engagement": 20, "demographics": 10, "media": 5, "prestige": 5}
        factors = scoring.score_property(self.unmeasured_engagement(), weights)["factors"]
        self.assertAlmostEqual(factors["audience"]["weight"], 60 * 100 / 80)
        self.assertAlmostEqual(factors["prestige"]["weight"], 5 * 100 / 80)
        self.assertAlmostEqual(sum(item["weight"] for item in factors.values()), 100)

    def test_when_the_measured_factors_have_no_weight_the_defaults_are_used(self):
        only_engagement = {"audience": 0, "engagement": 100, "demographics": 0, "media": 0, "prestige": 0}
        result = scoring.score_property(self.unmeasured_engagement(), only_engagement)
        self.assertAlmostEqual(sum(item["weight"] for item in result["factors"].values()), 100)
        self.assertGreater(result["total"], 0)

    def test_nothing_measured_scores_zero_without_crashing(self):
        empty = {"annual_audience_reach": "", "engagement_per_post": "", "high_income_share_pct": "",
                 "broadcast_tier": "", "prestige_rating": ""}
        self.assertEqual(scoring.score_property(empty)["total"], 0)

    def test_any_blank_factor_is_treated_the_same_way(self):
        prop = make_property(100_000, 500, 30, "", 5)  # no broadcast tier
        result = scoring.score_property(prop)
        self.assertEqual(result["unmeasured"], ["media"])
        self.assertAlmostEqual(sum(item["weight"] for item in result["factors"].values()), 100)

    def test_ranking_still_works_with_an_unmeasured_factor(self):
        good = make_property(5_000_000, 3_000, 40, 9, 9)
        unmeasured = make_property(5_000, "", 20, 2, 3)
        ranked = scoring.rank_properties([unmeasured, good])
        self.assertEqual([pair[0] for pair in ranked], [good, unmeasured])
        self.assertTrue(all(0 <= pair[1]["total"] <= 100 for pair in ranked))

    def test_redistribute_weights_directly(self):
        result = scoring.redistribute_weights({"a": 40, "b": 40, "c": 20}, ["a", "b"])
        self.assertEqual(result, {"a": 50, "b": 50, "c": 0})


class ConfidenceTests(unittest.TestCase):
    def test_every_factor_reports_the_confidence_from_the_data(self):
        prop = make_property(
            1000, 500, 30, 5, 5,
            engagement_followers=5_000,
            audience_confidence="published",
            engagement_confidence="calculated",
            high_income_confidence="estimate",
            broadcast_confidence="estimate",
            prestige_confidence="estimate",
        )
        labels = {f: item["confidence"] for f, item in scoring.score_property(prop)["factors"].items()}
        self.assertEqual(
            labels,
            {"audience": "published", "engagement": "calculated", "demographics": "estimate", "media": "estimate", "prestige": "estimate"},
        )

    def test_every_factor_has_a_confidence_column_and_an_input_column(self):
        self.assertEqual(set(scoring.CONFIDENCE_COLUMN), set(scoring.FACTOR_LABELS))
        self.assertEqual(set(scoring.INPUT_COLUMN), set(scoring.FACTOR_LABELS))


class AudienceScaleTests(unittest.TestCase):
    """The audience scale was set for the real data, which runs from 150 to 1.8 million."""

    REAL_AUDIENCES = {"club": 150, "junior event": 3_000, "player": 6_369, "challenger": 20_000, "premium": 1_848_000}

    def score(self, audience):
        return scoring.factor_scores(make_property(audience, 3, 30, 5, 5))["audience"]

    def test_the_smallest_real_audience_still_scores_above_zero(self):
        self.assertGreater(self.score(150), 0)

    def test_the_largest_real_audience_leaves_headroom_below_ten(self):
        self.assertLess(self.score(1_848_000), 9)

    def test_real_audiences_stay_in_order_and_are_well_spread(self):
        scores = [self.score(a) for a in sorted(self.REAL_AUDIENCES.values())]
        self.assertEqual(scores, sorted(scores))
        # Each is at least half a point apart, so no two properties look the same.
        self.assertTrue(all(b - a > 0.5 for a, b in zip(scores, scores[1:])), scores)

    def test_the_bounds_are_100_to_10_million(self):
        self.assertEqual(scoring.AUDIENCE_FLOOR, 100)
        self.assertEqual(scoring.AUDIENCE_CEILING, 10_000_000)


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
