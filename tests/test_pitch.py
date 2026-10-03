"""Checks that the brand-facing pitch is filled in correctly.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pitch
from unittest import mock

from data_loader import load_activations, load_brands, load_category_fit, load_properties
from display import clean_name
from matching import match_brands

BANDS = ["under18", "18_24", "25_34", "35_54", "55plus"]

# Words and symbols that belong in the internal analysis, never in the pitch.
# Words are matched as whole words, so "scoreboard" in an activation idea is fine.
INTERNAL_WORDS = ["score", "scores", "rated", "overlap", "points"]
INTERNAL_SYMBOLS = ["/ 100", "/10", "uk link", "| factor", "£"]


def internal_language_in(text):
    """Return any internal-analysis language found in the text (empty list = clean)."""
    lowered = text.lower()
    found = [word for word in INTERNAL_WORDS if re.search(rf"\b{word}\b", lowered)]
    return found + [symbol for symbol in INTERNAL_SYMBOLS if symbol in lowered]


def make_property(ages, high_income=42, **changes):
    """A made-up property, so these tests do not depend on your CSVs."""
    prop = {
        "name": "Test Open",
        "property_type": "premium_tournament",
        "description": "A test tournament",
        "annual_audience_reach": 12_000_000,
        "engagement_per_post": 900,  # what the score uses; makes engagement "measurable"
        "engagement_rate_pct": 4.5,
        "high_income_share_pct": high_income,
        "broadcast_tier": 9,
        "is_placeholder": False,
    }
    for band, pct in zip(BANDS, ages):
        prop[f"age_{band}_pct"] = pct
    prop.update(changes)
    return prop


def make_match(ages, fit=10, **brand_changes):
    """A made-up brand match. `ages` is the brand's target customer age profile."""
    brand = {
        "name": "Test Brand",
        "category": "watches",
        "uk_link": "SECRET-UK-LINK",
        "is_placeholder": False,
    }
    for band, pct in zip(BANDS, ages):
        brand[f"target_age_{band}_pct"] = pct
    brand.update(brand_changes)
    return {
        "brand": brand,
        "category_label": "luxury watch",
        "fit": fit,
        "total": 88.4,
        "overlap_pct": 85,
        "reasons": ["INTERNAL-REASON"],
    }


# Property audience: biggest group is 35-54. Brand's core customers are also 35-54.
PROP_AGES = [8, 12, 20, 35, 25]
BRAND_AGES = [0, 5, 25, 45, 25]

ACTIVATIONS = [
    {"category": "watches", "activation": "Official timekeeper with branded clocks"},
    {"category": "watches", "activation": "VIP hospitality hosted in the brand's name"},
    {"category": "watches", "activation": "Trophy presentation moment"},
    {"category": "watches", "activation": "Fourth idea"},
    {"category": "cars", "activation": "Car idea"},
]


def make_pitch(prop=None, match=None, activations=ACTIVATIONS):
    return pitch.generate_pitch(
        prop or make_property(PROP_AGES), match or make_match(BRAND_AGES), activations
    )


def section(text, heading):
    """The text under one heading, up to the next heading."""
    after = text.split(heading, 1)[1]
    return after.split("\n## ", 1)[0]


def bullets_under_why(text):
    return [line for line in section(text, "## Why Test Brand").splitlines() if line.startswith("- ")]


class NumberInWordsTests(unittest.TestCase):
    def test_millions(self):
        self.assertEqual(pitch.in_words(12_000_000), "12 million")
        self.assertEqual(pitch.in_words(250_000_000), "250 million")
        self.assertEqual(pitch.in_words(1_000_000), "1 million")

    def test_decimals_are_kept_to_one_place(self):
        self.assertEqual(pitch.in_words(1_234_567), "1.2 million")
        self.assertEqual(pitch.in_words(2_500_000), "2.5 million")

    def test_billions(self):
        self.assertEqual(pitch.in_words(2_000_000_000), "2 billion")

    def test_numbers_under_a_million_use_commas(self):
        self.assertEqual(pitch.in_words(150_000), "150,000")
        self.assertEqual(pitch.in_words(8_000), "8,000")
        self.assertEqual(pitch.in_words(999), "999")


class PitchLayoutTests(unittest.TestCase):
    def test_headline_names_property_and_brand(self):
        self.assertEqual(make_pitch().splitlines()[0], "# Partnership opportunity: Test Open × Test Brand")

    def test_has_the_five_sections_in_order(self):
        text = make_pitch()
        positions = [
            text.index("# Partnership opportunity"),
            text.index("## The property"),
            text.index("## Why Test Brand"),
            text.index("## Activation ideas"),
            text.index("## Next steps"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_large_numbers_are_in_words(self):
        text = make_pitch()
        self.assertIn("Audience reach: 12 million people", text)
        self.assertNotIn("12,000,000", text)

    def test_no_internal_language_and_no_money(self):
        text = make_pitch()
        self.assertEqual(internal_language_in(text), [])
        self.assertNotIn("INTERNAL-REASON", text)
        self.assertNotIn("SECRET-UK-LINK", text)

    def test_the_language_check_itself_works(self):
        self.assertEqual(internal_language_in("Commercial score: 80 / 100"), ["score", "/ 100"])
        self.assertEqual(internal_language_in("Branded scoreboard clocks"), [])

    def test_disclaimer_depends_on_what_is_real(self):
        # Real property and real brand: no disclaimer at all.
        self.assertNotIn("placeholder data", make_pitch())
        self.assertNotIn("Illustrative draft", make_pitch())
        # Placeholder property: the original warning.
        sample_property = make_pitch(prop=make_property(PROP_AGES, is_placeholder=True))
        self.assertIn("Draft built from placeholder data", sample_property)
        # Real property but an illustrative brand category: says so, and that it is not a real proposal.
        illustrative_brand = make_pitch(match=make_match(BRAND_AGES, is_placeholder=True))
        self.assertIn("Illustrative draft. The brand shown is an example of its category, not a real company", illustrative_brand)
        self.assertIn("not a real proposal", illustrative_brand)
        self.assertNotIn("invented examples", illustrative_brand)


class NamesAndSignoffTests(unittest.TestCase):
    def test_placeholder_is_hidden_from_names_everywhere_in_the_pitch(self):
        prop = make_property(PROP_AGES, name="Placeholder Test Open")
        match = make_match(BRAND_AGES, name="Placeholder Test Brand")
        text = pitch.generate_pitch(prop, match, ACTIVATIONS)
        self.assertEqual(text.splitlines()[0], "# Partnership opportunity: Test Open × Test Brand")
        self.assertIn("## Why Test Brand", text)
        self.assertIn("could work for Test Brand.", text)
        self.assertNotIn("Placeholder", text)  # the lower-case "placeholder data" banner is separate

    def test_pitch_ends_with_the_sign_off(self):
        last_line = [line for line in make_pitch().splitlines() if line.strip()][-1]
        self.assertEqual(last_line, "Prepared by Aaron Ventura, Partnerships")

    def test_sign_off_uses_the_constants_at_the_top_of_pitch_py(self):
        with mock.patch.object(pitch, "SIGNOFF_NAME", "Test Person"), mock.patch.object(pitch, "SIGNOFF_TITLE", "Test Title"):
            last_line = [line for line in make_pitch().splitlines() if line.strip()][-1]
        self.assertEqual(last_line, "Prepared by Test Person, Test Title")

    def test_sign_off_is_left_out_when_the_name_is_empty(self):
        with mock.patch.object(pitch, "SIGNOFF_NAME", ""):
            self.assertNotIn("Prepared by", make_pitch())

    def test_sign_off_without_a_title(self):
        with mock.patch.object(pitch, "SIGNOFF_TITLE", ""):
            last_line = [line for line in make_pitch().splitlines() if line.strip()][-1]
        self.assertEqual(last_line, "Prepared by Aaron Ventura")


class StatsTests(unittest.TestCase):
    def test_engagement_shown_only_when_it_is_a_strength(self):
        threshold = pitch.ENGAGEMENT_MIN_PCT
        strong = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=threshold))
        weak = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=threshold - 0.1))
        self.assertIn("Social media engagement rate", strong)
        self.assertNotIn("Social media engagement rate", weak)

    def test_higher_income_is_not_listed_as_a_stat(self):
        # Low engagement leaves room for the purchasing-power benefit (see BenefitPriorityTests).
        text = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=1))
        self.assertNotIn("higher-income", section(text, "## The property"))
        # It still appears once, in the benefits.
        self.assertEqual(text.count("higher-income"), 1)

    def test_audience_reach_is_always_listed(self):
        stats = section(make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=0, broadcast_tier=0)), "## The property")
        self.assertIn("Audience reach: 12 million people", stats)

    def test_a_players_audience_is_listed_as_instagram_followers(self):
        prop = make_property(PROP_AGES, property_type="player", annual_audience_reach=6_369)
        stats = section(make_pitch(prop=prop), "## The property")
        self.assertIn("Instagram followers: 6,369", stats)
        self.assertNotIn("Audience reach", stats)

    def test_broadcast_coverage_is_shown_only_when_it_is_a_strength(self):
        threshold = pitch.BROADCAST_MIN_TIER
        strong = section(make_pitch(prop=make_property(PROP_AGES, broadcast_tier=threshold)), "## The property")
        weak = section(make_pitch(prop=make_property(PROP_AGES, broadcast_tier=threshold - 1)), "## The property")
        self.assertIn("Broadcast coverage: live streaming", strong)
        self.assertNotIn("Broadcast coverage", weak)

    def test_broadcast_coverage_uses_the_rubric_wording(self):
        stats = section(make_pitch(prop=make_property(PROP_AGES, broadcast_tier=9)), "## The property")
        self.assertIn("Broadcast coverage: live free-to-air television", stats)

    def test_no_media_impressions_figure_remains(self):
        self.assertNotIn("impressions", make_pitch().lower())

    def test_unmeasurable_engagement_is_never_shown_or_praised(self):
        # No account at all, and a blank per-post figure.
        cases = [
            {"engagement_per_post": "", "engagement_rate_pct": "", "engagement_followers": ""},
            {"engagement_per_post": "", "engagement_rate_pct": 9.0},
        ]
        for case in cases:
            text = make_pitch(prop=make_property(PROP_AGES, **case))
            self.assertNotIn("engagement rate", text, case)
            self.assertNotIn("highly engaged", text, case)


class BenefitTests(unittest.TestCase):
    def test_largest_audience_group_benefit(self):
        text = make_pitch()
        self.assertIn("Your core customers, aged 35–54, are the tournament's largest audience group.", text)

    def test_significant_part_benefit(self):
        # Brand's core group is 25-34. It is 28% of the audience, not the largest group.
        prop = make_property([5, 10, 28, 40, 17])
        match = make_match([0, 5, 60, 25, 10])
        text = make_pitch(prop=prop, match=match)
        self.assertIn("aged 25–34, make up a significant part of the tournament's audience", text)

    def test_small_core_group_falls_back_to_best_shared_group(self):
        # Brand's core group is 35-54, but only 5% of this audience is that age.
        prop = make_property([2, 80, 10, 5, 3], property_type="university_team")
        match = make_match([20, 20, 20, 30, 10])
        text = make_pitch(prop=prop, match=match)
        self.assertIn("The team gives you access to customers aged 18–24, one of your key age groups.", text)

    def test_category_benefit_depends_on_fit(self):
        self.assertIn("natural home for luxury watch brands like yours", make_pitch(match=make_match(BRAND_AGES, fit=9)))
        self.assertIn("good setting for luxury watch brands like yours", make_pitch(match=make_match(BRAND_AGES, fit=6)))
        weak = make_pitch(match=make_match(BRAND_AGES, fit=3))
        self.assertNotIn("luxury watch brands", weak)

    def test_purchasing_power_benefit_depends_on_income_share(self):
        # Engagement is kept low so that it does not take up one of the three places.
        high = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=1))
        self.assertIn("42% of the audience is in higher-income brackets", high)
        low_income = make_pitch(prop=make_property(PROP_AGES, high_income=12, engagement_rate_pct=1))
        self.assertNotIn("higher-income brackets, giving", low_income)

    def test_always_two_or_three_benefits(self):
        # Strongest case: all four benefits apply, but only three are kept.
        self.assertEqual(len(bullets_under_why(make_pitch())), 3)
        # Weakest case: only the customer benefit applies, so a reach benefit is added.
        weak = make_pitch(
            prop=make_property(PROP_AGES, high_income=5, engagement_rate_pct=1),
            match=make_match(BRAND_AGES, fit=1),
        )
        self.assertEqual(len(bullets_under_why(weak)), 2)
        self.assertIn("Your brand would reach 12 million people.", weak)

    def test_reach_fallback_for_a_player_talks_about_followers(self):
        prop = make_property(PROP_AGES, high_income=5, engagement_rate_pct=1, property_type="player", annual_audience_reach=6_369)
        weak = make_pitch(prop=prop, match=make_match(BRAND_AGES, fit=1))
        self.assertIn("Your brand would reach 6,369 followers.", weak)


ENGAGEMENT_BULLET = "A highly engaged following, well above typical engagement rates."


class EngagementBenefitTests(unittest.TestCase):
    def test_engagement_benefit_appears_at_or_above_the_threshold(self):
        at_threshold = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=pitch.ENGAGEMENT_MIN_PCT))
        self.assertIn(ENGAGEMENT_BULLET, at_threshold)

    def test_engagement_benefit_is_left_out_below_the_threshold(self):
        below = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=pitch.ENGAGEMENT_MIN_PCT - 0.1))
        self.assertNotIn("highly engaged", below)

    def test_it_uses_the_same_threshold_constant_as_the_stats_line(self):
        with mock.patch.object(pitch, "ENGAGEMENT_MIN_PCT", 7):
            text = make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=5))
        self.assertNotIn("highly engaged", text)
        self.assertNotIn("Social media engagement rate", text)


class BenefitPriorityTests(unittest.TestCase):
    def test_priority_is_audience_then_engagement_then_category_then_purchasing_power(self):
        # All four apply, so purchasing power (the lowest priority) is the one dropped.
        bullets = bullets_under_why(make_pitch())
        self.assertEqual(len(bullets), 3)
        self.assertIn("Your core customers", bullets[0])
        self.assertIn("highly engaged", bullets[1])
        self.assertIn("natural home", bullets[2])
        self.assertNotIn("higher-income", "\n".join(bullets))

    def test_without_engagement_purchasing_power_takes_the_third_place(self):
        bullets = bullets_under_why(make_pitch(prop=make_property(PROP_AGES, engagement_rate_pct=1)))
        self.assertEqual(len(bullets), 3)
        self.assertIn("Your core customers", bullets[0])
        self.assertIn("natural home", bullets[1])
        self.assertIn("higher-income", bullets[2])

    def test_never_more_than_three(self):
        for engagement in (0, 1, 4, 9):
            for fit in (1, 6, 9):
                for income in (5, 42):
                    text = make_pitch(
                        prop=make_property(PROP_AGES, high_income=income, engagement_rate_pct=engagement),
                        match=make_match(BRAND_AGES, fit=fit),
                    )
                    self.assertIn(len(bullets_under_why(text)), (2, 3))


class CategoryWordingTests(unittest.TestCase):
    def pitch_for(self, property_type, fit, name="Test Open"):
        prop = make_property(PROP_AGES, property_type=property_type, name=name)
        return make_pitch(prop=prop, match=make_match(BRAND_AGES, fit=fit))

    def test_events_are_a_natural_home(self):
        for event_type in ("premium_tournament", "challenger_tournament", "junior_event"):
            noun = pitch.PROPERTY_NOUN[event_type]
            self.assertIn(f"The {noun} is a natural home for luxury watch brands like yours.", self.pitch_for(event_type, 9))

    def test_a_player_is_a_natural_ambassador_and_is_named(self):
        text = self.pitch_for("player", 9, name="Placeholder Rising Player")
        self.assertIn("Rising Player is a natural ambassador for luxury watch brands like yours.", text)
        self.assertNotIn("natural home", text)
        self.assertNotIn("The player is", text)

    def test_a_university_team_is_a_natural_partner(self):
        text = self.pitch_for("university_team", 9)
        self.assertIn("The team is a natural partner for luxury watch brands like yours.", text)
        self.assertNotIn("natural home", text)

    def test_good_fit_wording_follows_the_same_style(self):
        self.assertIn("is a good setting for luxury watch brands", self.pitch_for("premium_tournament", 6))
        self.assertIn("is a good ambassador for luxury watch brands", self.pitch_for("player", 6))
        self.assertIn("is a good partner for luxury watch brands", self.pitch_for("university_team", 6))

    def test_weak_fit_leaves_the_bullet_out_for_every_type(self):
        for property_type in pitch.CATEGORY_FIT_STYLE:
            self.assertNotIn("luxury watch brands", self.pitch_for(property_type, 3), property_type)

    def test_an_unlisted_property_type_is_worded_like_an_event(self):
        text = self.pitch_for("exhibition_match", 9)
        self.assertIn("The exhibition match is a natural home for luxury watch brands like yours.", text)

    def test_every_sample_property_type_has_a_wording_style(self):
        for prop in load_properties():
            self.assertIn(prop["property_type"], pitch.CATEGORY_FIT_STYLE, prop["property_type"])


class EngagementRequirementTests(unittest.TestCase):
    """The "highly engaged" bullet needs a strong RATE and a real VOLUME of engagement."""

    def bullet_shown(self, rate, per_post, **extra):
        prop = make_property(PROP_AGES, engagement_rate_pct=rate, engagement_per_post=per_post, **extra)
        return ENGAGEMENT_BULLET in make_pitch(prop=prop)

    def test_the_new_constant_is_100_engagements_per_post(self):
        self.assertEqual(pitch.ENGAGEMENT_MIN_PER_POST, 100)

    def test_both_conditions_met_shows_the_bullet(self):
        self.assertTrue(self.bullet_shown(rate=pitch.ENGAGEMENT_MIN_PCT, per_post=pitch.ENGAGEMENT_MIN_PER_POST))
        self.assertTrue(self.bullet_shown(rate=13.8, per_post=878))

    def test_exactly_at_both_thresholds_counts(self):
        self.assertTrue(self.bullet_shown(rate=4, per_post=100))

    def test_a_high_rate_on_a_tiny_account_is_not_enough(self):
        # 20% of 400 followers is only 80 engagements per post.
        self.assertFalse(self.bullet_shown(rate=20, per_post=99))
        self.assertFalse(self.bullet_shown(rate=20, per_post=23))

    def test_lots_of_engagement_but_a_low_rate_is_not_enough(self):
        # 2,025 per post on a 70,000-follower account is a 2.9% rate.
        self.assertFalse(self.bullet_shown(rate=2.9, per_post=2_025))
        self.assertFalse(self.bullet_shown(rate=3.9, per_post=5_000))

    def test_neither_condition_met(self):
        self.assertFalse(self.bullet_shown(rate=1, per_post=10))

    def test_an_unmeasurable_engagement_never_shows_the_bullet(self):
        self.assertFalse(self.bullet_shown(rate="", per_post=""))

    def test_both_thresholds_are_read_from_the_named_constants(self):
        with mock.patch.object(pitch, "ENGAGEMENT_MIN_PER_POST", 1_000):
            self.assertFalse(self.bullet_shown(rate=13.8, per_post=878))
            self.assertTrue(self.bullet_shown(rate=13.8, per_post=1_000))
        with mock.patch.object(pitch, "ENGAGEMENT_MIN_PCT", 20):
            self.assertFalse(self.bullet_shown(rate=13.8, per_post=878))
            self.assertTrue(self.bullet_shown(rate=20, per_post=878))

    def test_a_blocked_bullet_makes_room_for_the_next_benefit(self):
        # Without the engagement bullet, purchasing power can take the third place.
        prop = make_property(PROP_AGES, engagement_rate_pct=20, engagement_per_post=50)
        bullets = "\n".join(bullets_under_why(make_pitch(prop=prop)))
        self.assertNotIn("highly engaged", bullets)
        self.assertIn("higher-income", bullets)

    def test_the_rate_line_in_the_property_stats_still_follows_the_rate_alone(self):
        # Only the benefit needs the extra volume check. The stats line is a plain fact.
        prop = make_property(PROP_AGES, engagement_rate_pct=20, engagement_per_post=50)
        self.assertIn("Social media engagement rate: 20%", section(make_pitch(prop=prop), "## The property"))

    def test_the_real_data_shows_the_bullet_only_for_toby_samuel(self):
        shown = []
        for prop in load_properties():
            match = match_brands(prop, load_brands(), load_category_fit())["matches"][0]
            if ENGAGEMENT_BULLET in pitch.generate_pitch(prop, match, load_activations()):
                shown.append(prop["name"])
        self.assertEqual(shown, ["Toby Samuel"])  # the only one with a 4%+ rate AND 100+ per post


class EstimateWordingTests(unittest.TestCase):
    """Estimated figures must never read like facts: they get "about" or "An estimated"."""

    def audience_line(self, confidence, **changes):
        prop = make_property(PROP_AGES, audience_confidence=confidence, annual_audience_reach=3_000, **changes)
        return section(make_pitch(prop=prop), "## The property")

    def test_an_estimated_audience_is_prefixed_with_about(self):
        self.assertIn("Audience reach: about 3,000 people", self.audience_line("estimate"))

    def test_published_and_calculated_audiences_are_not_prefixed(self):
        for confidence in ("published", "calculated"):
            stats = self.audience_line(confidence)
            self.assertIn("Audience reach: 3,000 people", stats, confidence)
            self.assertNotIn("about", stats, confidence)

    def test_a_property_with_no_confidence_label_is_not_prefixed(self):
        self.assertIn("Audience reach: 12 million people", section(make_pitch(), "## The property"))

    def test_an_estimated_income_share_is_introduced_as_an_estimate(self):
        prop = make_property(PROP_AGES, engagement_rate_pct=1, high_income_confidence="estimate")
        bullets = "\n".join(bullets_under_why(make_pitch(prop=prop)))
        self.assertIn("An estimated 42% of the audience is in higher-income brackets, giving you", bullets)

    def test_a_published_income_share_is_not(self):
        prop = make_property(PROP_AGES, engagement_rate_pct=1, high_income_confidence="published")
        bullets = "\n".join(bullets_under_why(make_pitch(prop=prop)))
        self.assertIn("- 42% of the audience is in higher-income brackets", bullets)
        self.assertNotIn("estimated", bullets)

    def test_the_reach_fallback_also_says_about_for_an_estimate(self):
        prop = make_property(PROP_AGES, high_income=5, engagement_rate_pct=1, audience_confidence="estimate", annual_audience_reach=150)
        weak = make_pitch(prop=prop, match=make_match(BRAND_AGES, fit=1))
        self.assertIn("Your brand would reach about 150 people.", weak)

    def test_a_players_published_follower_count_is_stated_plainly(self):
        prop = make_property(PROP_AGES, property_type="player", annual_audience_reach=6_369, audience_confidence="published")
        self.assertIn("Instagram followers: 6,369", section(make_pitch(prop=prop), "## The property"))

    def test_engagement_rate_is_calculated_so_it_is_not_hedged(self):
        prop = make_property(PROP_AGES, engagement_rate_pct=13.8, engagement_confidence="calculated")
        self.assertIn("Social media engagement rate: 13.8%", section(make_pitch(prop=prop), "## The property"))


class RealDataPitchTests(unittest.TestCase):
    def pitch_for(self, property_id):
        prop = next(p for p in load_properties() if p["id"] == property_id)
        match = match_brands(prop, load_brands(), load_category_fit())["matches"][0]
        return pitch.generate_pitch(prop, match, load_activations())

    def test_estimated_audiences_say_about(self):
        self.assertIn("Audience reach: about 3,000 people", self.pitch_for("P03"))  # Roehampton, an estimate
        self.assertIn("Audience reach: about 150 people", self.pitch_for("P04"))    # Queen Mary, an estimate

    def test_published_or_calculated_audiences_are_stated_plainly(self):
        self.assertIn("Audience reach: 1.8 million people", self.pitch_for("P01"))  # a calculated sum
        self.assertIn("Audience reach: 20,000 people", self.pitch_for("P02"))       # published attendance
        self.assertIn("Instagram followers: 6,369", self.pitch_for("P05"))          # published follower count

    def test_the_ilkley_description_is_the_agreed_one(self):
        self.assertIn("ATP Challenger 125 and WTA 125 grass-court event in Ilkley, West Yorkshire.", self.pitch_for("P02"))

    def test_every_estimated_income_share_in_a_pitch_is_flagged_as_an_estimate(self):
        for property_id in ("P01", "P02", "P03", "P04", "P05"):
            text = self.pitch_for(property_id)
            if "higher-income" in text:
                self.assertIn("An estimated", text, property_id)


class SoftenedAgeClaimsTests(unittest.TestCase):
    """Where the age profile is only an estimate, audience-age claims are worded as "likely"."""

    def why_bullets(self, confidence, prop_ages=PROP_AGES, brand_ages=BRAND_AGES, **prop_changes):
        prop = make_property(prop_ages, **prop_changes)
        if confidence is not None:
            prop["age_profile_confidence"] = confidence
        return bullets_under_why(make_pitch(prop=prop, match=make_match(brand_ages)))[0]

    # --- the core customers are the largest group ---
    def test_largest_group_claim_is_softened_for_an_estimate(self):
        self.assertEqual(
            self.why_bullets("estimate"),
            "- Your core customers, aged 35–54, are likely the tournament's largest audience group.",
        )

    def test_largest_group_claim_is_plain_when_published_or_calculated(self):
        for confidence in ("published", "calculated", None):
            self.assertEqual(
                self.why_bullets(confidence),
                "- Your core customers, aged 35–54, are the tournament's largest audience group.",
                confidence,
            )

    # --- a significant part of the audience ---
    def test_significant_part_claim(self):
        ages, brand = [5, 10, 28, 40, 17], [0, 5, 60, 25, 10]
        self.assertEqual(
            self.why_bullets("estimate", ages, brand),
            "- Your core customers, aged 25–34, are likely to make up a significant part of the tournament's audience.",
        )
        self.assertEqual(
            self.why_bullets("calculated", ages, brand),
            "- Your core customers, aged 25–34, make up a significant part of the tournament's audience.",
        )

    # --- access to a shared age group ---
    def test_access_claim(self):
        ages, brand = [2, 80, 10, 5, 3], [20, 20, 20, 30, 10]
        soft = self.why_bullets("estimate", ages, brand, property_type="university_team")
        plain = self.why_bullets("published", ages, brand, property_type="university_team")
        self.assertEqual(soft, "- The team is likely to give you access to customers aged 18–24, one of your key age groups.")
        self.assertEqual(plain, "- The team gives you access to customers aged 18–24, one of your key age groups.")

    # --- families at youth events ---
    def test_the_families_claim_is_never_hedged(self):
        # It describes the kind of event (a junior event), not the estimated age profile.
        for confidence in ("estimate", "calculated", "published", None):
            bullet = self.why_bullets(confidence, [45, 4, 4, 42, 5], property_type="junior_event", audience_includes_minors=True)
            self.assertEqual(bullet, f"- {FAMILIES_BULLET}", confidence)
            self.assertNotIn("likely", bullet, confidence)

    # --- only the age claims are softened ---
    def test_other_claims_are_not_hedged_by_the_age_profile(self):
        prop = make_property(PROP_AGES, engagement_rate_pct=1, age_profile_confidence="estimate")
        bullets = "\n".join(bullets_under_why(make_pitch(prop=prop)))
        self.assertIn("The tournament is a natural home for luxury watch brands like yours.", bullets)
        self.assertIn("42% of the audience is in higher-income brackets", bullets)

    def test_the_hedge_depends_only_on_the_age_profile_not_the_other_figures(self):
        prop = make_property(PROP_AGES, age_profile_confidence="calculated", audience_confidence="estimate")
        self.assertIn("are the tournament's largest audience group", bullets_under_why(make_pitch(prop=prop))[0])

    def test_under_18s_are_still_never_called_customers_when_softened(self):
        text = self.why_bullets("estimate", [55, 5, 5, 30, 5], [60, 0, 5, 35, 0], property_type="junior_event", audience_includes_minors=True).lower()
        for phrase in UNDER_18_PHRASES:
            self.assertNotIn(phrase, text)


class RealDataAgeClaimTests(unittest.TestCase):
    def audience_bullet(self, property_id):
        prop = next(p for p in load_properties() if p["id"] == property_id)
        match = match_brands(prop, load_brands(), load_category_fit())["matches"][0]
        text = pitch.generate_pitch(prop, match, load_activations())
        return [line for line in section(text, "## Why ").splitlines() if line.startswith("- ")][0]

    def test_every_real_pitch_hedges_its_age_claim_because_the_profiles_are_estimates(self):
        for property_id in ("P01", "P02", "P04", "P05"):
            self.assertIn("likely", self.audience_bullet(property_id), property_id)

    def test_the_junior_event_states_its_families_claim_plainly(self):
        self.assertEqual(self.audience_bullet("P03"), f"- {FAMILIES_BULLET}")

    def test_the_real_data_has_no_firm_age_profile_yet(self):
        # This is why every pitch is hedged. When a profile is researched, update its confidence label
        # and its pitch will state the claim plainly.
        for prop in load_properties():
            self.assertEqual(prop["age_profile_confidence"], "estimate", prop["id"])


FAMILIES_BULLET = "The event reaches families: parents and young players together."
UNDER_18_PHRASES = ["customers aged under 18", "access to customers aged under 18", "under 18"]


class YouthAudienceTests(unittest.TestCase):
    def junior_pitch(self, brand_ages):
        prop = make_property([55, 5, 5, 30, 5], property_type="junior_event", audience_includes_minors=True)
        return make_pitch(prop=prop, match=make_match(brand_ages))

    def test_youth_events_talk_about_families(self):
        text = self.junior_pitch([60, 0, 5, 35, 0])
        self.assertEqual(bullets_under_why(text)[0], f"- {FAMILIES_BULLET}")

    def test_under_18s_are_never_described_as_the_brands_customers(self):
        # Brands whose target customers are mostly under 18 are the hardest case.
        for brand_ages in ([60, 0, 5, 35, 0], [100, 0, 0, 0, 0], [0, 0, 0, 50, 50]):
            text = self.junior_pitch(brand_ages).lower()
            for phrase in UNDER_18_PHRASES:
                self.assertNotIn(phrase, text, f"{brand_ages}: found '{phrase}'")

    def test_families_wording_is_only_for_properties_with_minors(self):
        self.assertNotIn("reaches families", make_pitch())

    def test_adult_events_also_never_call_under_18s_customers(self):
        # An adult event matched to a brand whose core customers are under 18.
        text = make_pitch(match=make_match([60, 0, 5, 35, 0])).lower()
        for phrase in UNDER_18_PHRASES:
            self.assertNotIn(phrase, text)
        self.assertIn("aged 35–54", text)  # described by the adult group instead


class ActivationAndNextStepsTests(unittest.TestCase):
    def test_shows_at_most_three_activations_from_the_right_category(self):
        text = make_pitch()
        self.assertIn("1. Official timekeeper with branded clocks", text)
        self.assertIn("3. Trophy presentation moment", text)
        self.assertNotIn("Fourth idea", text)
        self.assertNotIn("Car idea", text)

    def test_next_steps_asks_for_a_30_minute_call_and_refers_to_the_ideas(self):
        steps = section(make_pitch(), "## Next steps")
        self.assertIn("30-minute call", steps)
        self.assertIn("partnership options", steps)
        self.assertIn("activation ideas above", steps)
        self.assertIn("Test Brand", steps)

    def test_missing_activations_do_not_crash_or_point_to_ideas_above(self):
        text = make_pitch(activations=[])
        self.assertIn("No activation ideas listed yet", text)
        steps = section(text, "## Next steps")
        self.assertIn("30-minute call", steps)
        self.assertNotIn("above", steps)


class SampleDataTests(unittest.TestCase):
    def test_no_sample_pitch_describes_under_18s_as_customers(self):
        brands, fit, activations = load_brands(), load_category_fit(), load_activations()
        for prop in load_properties():
            for match in match_brands(prop, brands, fit, top_n=99)["matches"]:  # every brand, not just the top 3
                text = pitch.generate_pitch(prop, match, activations).lower()
                name = f"{prop['name']} x {match['brand']['name']}"
                for phrase in UNDER_18_PHRASES:
                    self.assertNotIn(phrase, text, f"{name}: found '{phrase}'")
                if prop["audience_includes_minors"]:
                    # Stated plainly, even though the age profile is an estimate.
                    self.assertIn(FAMILIES_BULLET.lower(), text, name)
                    self.assertNotIn("likely to reach families", text, name)

    def test_every_sample_property_produces_a_clean_pitch(self):
        brands, fit, activations = load_brands(), load_category_fit(), load_activations()
        for prop in load_properties():
            for match in match_brands(prop, brands, fit)["matches"]:
                text = pitch.generate_pitch(prop, match, activations)
                name = f"{prop['name']} x {match['brand']['name']}"
                self.assertIn(clean_name(match["brand"]["name"]), text, name)
                self.assertNotIn("Placeholder", text, name)
                self.assertIn("Prepared by", text, name)
                self.assertNotIn("No activation ideas listed yet", text, name)
                self.assertEqual(internal_language_in(text), [], name)
                count = sum(1 for line in section(text, "## Why ").splitlines() if line.startswith("- "))
                self.assertIn(count, (2, 3), name)


if __name__ == "__main__":
    unittest.main()
