"""Drives the real Streamlit app without a browser, the way a person would
(picking properties, dragging sliders, choosing a brand), and checks what appears.

These tests need Streamlit. If it is not installed they are skipped. Run them with:
    .venv/bin/python -m unittest discover tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT))

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Streamlit is not installed in this Python
    AppTest = None

import scoring
from data_loader import load_properties
from display import clean_name, type_label

APP_FILE = str(PROJECT / "app.py")
FACTORS = list(scoring.FACTOR_LABELS)  # slider order: audience, engagement, demographics, media, prestige


def start_app():
    return AppTest.from_file(APP_FILE, default_timeout=30).run()


def ranking_scores(at):
    """The Score column of the ranking table (the first table on the page)."""
    return list(at.dataframe[0].value["Score"])


def ranking_names(at):
    return list(at.dataframe[0].value["Property"])


def pitch_markdown(at):
    """The rendered pitch, or None if no pitch is on the page."""
    for element in at.markdown:
        if "# Partnership opportunity" in element.value:
            return element.value
    return None


def analysis_title(at):
    """The property name line under the Analysis heading."""
    for element in at.markdown:
        if element.value.startswith("**") and " · " in element.value and "match score" not in element.value:
            return element.value
    return None


def everything_displayed(at):
    """All the text the app shows, except the placeholder-data warning banner."""
    pieces = [e.value for e in at.markdown] + [e.value for e in at.caption] + [e.value for e in at.header]
    pieces += [e.value for e in at.subheader]
    # The test framework gives each picker's options as the text a person sees.
    pieces += [str(option) for box in at.sidebar.selectbox for option in box.options]
    pieces += [str(option) for box in at.main.selectbox for option in box.options]
    for table in at.dataframe:
        pieces.append(table.value.to_string())
    return "\n".join(pieces)


def set_weights(at, **weights):
    """Set sliders by factor name, for example set_weights(at, audience=50, prestige=0)."""
    for factor, value in weights.items():
        at.sidebar.slider[FACTORS.index(factor)].set_value(value)
    return at.run()


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class AppLayoutTests(unittest.TestCase):
    def test_app_runs_without_errors(self):
        self.assertEqual(len(start_app().exception), 0)

    def test_banner_says_properties_are_real_and_brands_are_illustrative(self):
        banners = [w.value for w in start_app().warning]
        banner = next((text for text in banners if "Real properties, illustrative brands" in text), None)
        self.assertIsNotNone(banner, banners)
        self.assertIn("as of 2 October 2026", banner)
        self.assertIn("sourced or estimated", banner)
        self.assertIn("illustrative categories, not real companies", banner)
        self.assertIn("illustrative only, not real proposals", banner)
        self.assertNotIn("PLACEHOLDER DATA", banner)

    def test_sections_appear_in_the_agreed_order(self):
        headers = [h.value for h in start_app().header if h.value not in ("Property", "Score weights")]
        self.assertEqual(headers, ["Property ranking", "Analysis", "Pitch"])

    def test_sidebar_has_a_property_picker_and_five_sliders_at_the_default_weights(self):
        at = start_app()
        self.assertEqual(len(at.sidebar.selectbox), 1)
        self.assertEqual([s.value for s in at.sidebar.slider], [scoring.DEFAULT_WEIGHTS[f] for f in FACTORS])

    def test_ranking_table_lists_every_property_best_first(self):
        at = start_app()
        scores = ranking_scores(at)
        self.assertEqual(len(scores), len(load_properties()))
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_ranking_table_shows_only_rank_property_type_and_score(self):
        table = start_app().dataframe[0].value
        self.assertEqual(list(table.columns), ["Rank", "Property", "Type", "Score"])

    def test_property_types_are_capitalised(self):
        types = set(start_app().dataframe[0].value["Type"])
        self.assertEqual(types, {type_label(p["property_type"]) for p in load_properties()})
        self.assertIn("Premium tournament", types)

    def test_placeholder_is_hidden_from_displayed_names_but_the_banner_stays(self):
        at = start_app()
        self.assertNotIn("Placeholder", everything_displayed(at))
        self.assertTrue(any("illustrative brands" in w.value for w in at.warning))

    def test_match_caption_is_the_agreed_wording(self):
        captions = [c.value for c in start_app().caption]
        self.assertIn("Match score combines audience overlap (60%) and category fit (40%). Brands marked '=' are tied.", captions)
        self.assertFalse(any("matching.py" in text for text in captions))

    def test_match_reasons_show_the_fit_number_once(self):
        text = "\n".join(m.value for m in start_app().markdown)
        self.assertIn("Category fit 10/10: luxury watch brands suit a premium tournament well.", text)
        self.assertNotIn("are rated", text)

    def test_heading_link_icons_are_hidden_across_the_whole_page(self):
        css = "\n".join(str(element.value) for element in start_app().get("html"))
        self.assertIn('[data-testid="stHeaderActionElements"] { display: none; }', css)
        self.assertNotIn(".st-key-", css)  # not limited to one box

    def test_pitch_headings_are_smaller_on_screen(self):
        text = pitch_markdown(start_app())
        self.assertIn("\n### Partnership opportunity", "\n" + text)
        self.assertNotIn("\n# ", "\n" + text)
        self.assertIn("#### The property", text)
        self.assertIn("Prepared by Aaron Ventura, Partnerships", text)

    def test_analysis_shows_the_score_breakdown_and_top_matches(self):
        at = start_app()
        self.assertEqual(len(at.metric), 1)
        breakdown = at.dataframe[1].value
        self.assertEqual(list(breakdown["Factor"]), list(scoring.FACTOR_LABELS.values()))
        self.assertAlmostEqual(breakdown["Points"].sum(), float(at.metric[0].value), delta=0.3)
        self.assertGreaterEqual(len([m for m in at.markdown if " · match score" in m.value]), 3)


def brand_picker(at):
    """The pitch's brand picker, found by its label (not its position on the page)."""
    return next(box for box in at.main.selectbox if box.label == "Brand for the pitch")


def pandas_isna(value):
    """True for None or NaN (how an empty table cell comes back)."""
    return value is None or value != value


def choose_property(at, property_id):
    prop = next(p for p in load_properties() if p["id"] == property_id)
    at.sidebar.selectbox[0].select(clean_name(prop["name"])).run()
    return at


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class ConfidenceDisplayTests(unittest.TestCase):
    def breakdown(self, at):
        return at.dataframe[1].value.set_index("Factor")

    def test_the_breakdown_has_a_confidence_column_next_to_each_figure(self):
        table = self.breakdown(start_app())
        self.assertEqual(list(table.columns), ["Figure", "Confidence", "Score (0-10)", "Weight", "Points"])
        # Queen's: the audience is calculated, engagement calculated, income an estimate.
        self.assertEqual(table.loc["Audience size", "Confidence"], "Calculated")
        self.assertEqual(table.loc["Social engagement", "Confidence"], "Calculated")
        self.assertEqual(table.loc["Purchasing power", "Confidence"], "Estimate")
        self.assertEqual(table.loc["Broadcast exposure", "Confidence"], "Estimate")
        self.assertEqual(table.loc["Prestige", "Confidence"], "Estimate")

    def test_estimates_are_labelled_for_every_property(self):
        for prop in load_properties():
            table = self.breakdown(choose_property(start_app(), prop["id"]))
            for factor_label, confidence in table["Confidence"].items():
                self.assertIn(confidence.lower().split(" ")[0], ("published", "calculated", "estimate", "not"), (prop["id"], factor_label))
            self.assertEqual(table.loc["Purchasing power", "Confidence"], "Estimate", prop["id"])

    def test_engagement_shows_per_post_with_the_rate_as_context(self):
        figure = self.breakdown(start_app()).loc["Social engagement", "Figure"]
        self.assertEqual(figure, "2,025 per post (median likes + comments) · rate 2.9% of 70,100 followers")

    def test_the_score_uses_engagements_per_post_not_the_rate(self):
        # Queen's has a low rate (2.9%) but the most engagements per post, so it scores well on engagement.
        table = self.breakdown(start_app())
        self.assertAlmostEqual(table.loc["Social engagement", "Score (0-10)"], 7.7, places=1)
        toby = self.breakdown(choose_property(start_app(), "P05"))  # a 13.8% rate, 878 per post
        self.assertAlmostEqual(toby.loc["Social engagement", "Score (0-10)"], 6.5, places=1)
        self.assertGreater(table.loc["Social engagement", "Score (0-10)"], toby.loc["Social engagement", "Score (0-10)"])

    def test_an_unmeasurable_factor_is_left_out_and_labelled_not_measured(self):
        table = self.breakdown(choose_property(start_app(), "P03"))  # Roehampton: no dedicated account
        self.assertEqual(table.loc["Social engagement", "Confidence"], "Not measured")
        self.assertEqual(table.loc["Social engagement", "Figure"], "Not measurable (no dedicated account)")
        self.assertTrue(pandas_isna(table.loc["Social engagement", "Score (0-10)"]))  # no score, not a neutral 5
        self.assertEqual(table.loc["Social engagement", "Points"], 0)
        self.assertEqual(table.loc["Social engagement", "Weight"], 0)

    def test_the_weights_set_and_the_weights_used_are_both_shown_when_one_is_redistributed(self):
        table = self.breakdown(choose_property(start_app(), "P03"))
        self.assertEqual(list(table.columns), ["Figure", "Confidence", "Score (0-10)", "Weight set", "Weight", "Points"])
        self.assertEqual(table.loc["Social engagement", "Weight set"], 20)
        self.assertEqual(table.loc["Audience size", "Weight set"], 25)
        self.assertAlmostEqual(table.loc["Audience size", "Weight"], 31.2, places=1)  # 25 x 100/80
        self.assertAlmostEqual(table["Weight"].sum(), 100, places=0)
        self.assertAlmostEqual(table["Points"].sum(), 41.7, delta=0.3)

    def test_a_notice_explains_the_redistribution(self):
        at = choose_property(start_app(), "P03")
        notices = [n.value for n in at.info]
        self.assertEqual(len(notices), 1)
        self.assertIn("Not measured: Social engagement (weight 20)", notices[0])
        self.assertIn("shared across the other factors in proportion to their weights", notices[0])
        self.assertIn("measured evidence only", notices[0])
        self.assertIn("still out of 100", notices[0])

    def test_no_notice_and_no_extra_column_when_everything_is_measured(self):
        at = start_app()  # Queen's
        self.assertEqual(len(at.info), 0)
        self.assertNotIn("Weight set", self.breakdown(at).columns)

    def test_the_redistribution_follows_the_sliders(self):
        at = choose_property(start_app(), "P03")
        at.sidebar.slider[FACTORS.index("audience")].set_value(60).run()
        table = self.breakdown(at)
        self.assertAlmostEqual(table["Weight"].sum(), 100, places=0)
        self.assertEqual(table.loc["Social engagement", "Weight"], 0)
        self.assertGreater(table.loc["Audience size", "Weight"], 31.2)  # the heavier slider counts for more

    def test_the_ranking_still_shows_a_score_out_of_100_for_a_property_with_an_unmeasured_factor(self):
        at = start_app()
        for score in ranking_scores(at):
            self.assertTrue(0 <= score <= 100)
        roehampton = clean_name(next(p for p in load_properties() if p["id"] == "P03")["name"])
        self.assertIn(roehampton, ranking_names(at))

    def test_the_audience_figure_is_described_by_property_type(self):
        self.assertEqual(self.breakdown(start_app()).loc["Audience size", "Figure"], "1.8 million people")
        player = self.breakdown(choose_property(start_app(), "P05"))
        self.assertEqual(player.loc["Audience size", "Figure"], "6,369 Instagram followers")

    def test_the_broadcast_figure_shows_the_tier_and_the_rubric_wording(self):
        table = self.breakdown(start_app())
        self.assertEqual(table.loc["Broadcast exposure", "Figure"], "Tier 9: live free-to-air television")
        self.assertEqual(table.loc["Broadcast exposure", "Score (0-10)"], 9.0)

    def test_the_confidence_labels_are_explained(self):
        captions = [c.value for c in start_app().caption]
        self.assertTrue(any("Published" in c and "Calculated" in c and "Estimate" in c for c in captions))

    def test_each_figures_source_is_listed_in_a_data_sources_panel(self):
        at = start_app()
        labels = [e.label for e in at.expander]
        self.assertIn("Data sources (collected 2026-10-02)", labels)
        sources = at.dataframe[2].value
        self.assertEqual(
            list(sources["Figure"]),
            ["Audience size", "Social engagement", "Purchasing power", "Broadcast exposure", "Prestige",
             "Audience age profile (used in matching)"],
        )
        self.assertIn("LTA, 2025", sources.iloc[0]["Source"])
        self.assertTrue(sources.iloc[0]["Link"] is None or pandas_isna(sources.iloc[0]["Link"]))  # no link for Queen's yet

    def test_source_links_are_shown_where_recorded(self):
        ilkley = choose_property(start_app(), "P02").dataframe[2].value
        self.assertEqual(
            ilkley.iloc[0]["Link"],
            "https://www.lta.org.uk/49c743/siteassets/events/ilkley/media/2025-lexus-ilkley-open-programme.pdf",
        )
        roehampton = choose_property(start_app(), "P03").dataframe[2].value
        self.assertEqual(
            roehampton.iloc[0]["Link"],
            "https://www.itftennis.com/en/tournament/j300-roehampton/gbr/2026/j-j300-gbr-2026-001/",
        )

    def test_the_caption_explains_why_engagement_is_scored_per_post(self):
        captions = " ".join(c.value for c in start_app().caption)
        self.assertIn("scored on engagements per post, not on the rate", captions)
        self.assertIn("flatters small accounts", captions)
        self.assertIn("Not measured", captions)

    def test_the_unresearched_age_profile_is_flagged_next_to_the_matches(self):
        captions = [c.value for c in start_app().caption]
        self.assertTrue(any("audience age profile" in c and "estimate" in c for c in captions))
        sources = start_app().dataframe[2].value
        self.assertEqual(sources.iloc[-1]["Confidence"], "Estimate")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class SliderTests(unittest.TestCase):
    def test_moving_a_slider_updates_the_ranking_live(self):
        before = ranking_scores(start_app())
        at = set_weights(start_app(), audience=100, engagement=0, demographics=0, media=0, prestige=0)
        after = ranking_scores(at)
        self.assertNotEqual(before, after)
        # With only audience counting, the top score is the best audience score x 10.
        best_audience = max(scoring.factor_scores(p)["audience"] for p in load_properties())
        self.assertAlmostEqual(after[0], best_audience * 10, places=3)

    def test_weights_are_rescaled_so_scores_stay_out_of_100(self):
        # Every slider at its maximum is the same as every slider at 20: scores stay within 0-100.
        at = set_weights(start_app(), audience=100, engagement=100, demographics=100, media=100, prestige=100)
        self.assertTrue(all(0 <= score <= 100 for score in ranking_scores(at)))
        equal = {f: 100 for f in FACTORS}
        expected = max(scoring.score_property(p, equal)["total"] for p in load_properties())
        self.assertAlmostEqual(ranking_scores(at)[0], expected, places=3)

    def test_all_zero_weights_show_an_error_and_fall_back_to_defaults(self):
        defaults = ranking_scores(start_app())
        at = set_weights(start_app(), audience=0, engagement=0, demographics=0, media=0, prestige=0)
        self.assertEqual(len(at.sidebar.error), 1)
        self.assertEqual(ranking_scores(at), defaults)

    def test_reset_button_restores_the_defaults(self):
        at = set_weights(start_app(), audience=0, prestige=100)
        at.sidebar.button[0].click().run()
        self.assertEqual([s.value for s in at.sidebar.slider], [scoring.DEFAULT_WEIGHTS[f] for f in FACTORS])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class PropertyPickerTests(unittest.TestCase):
    def test_choosing_another_property_changes_the_analysis_and_pitch(self):
        at = start_app()
        first_title = analysis_title(at)
        chosen = load_properties()[3]
        at.sidebar.selectbox[0].select(clean_name(chosen["name"])).run()
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual(first_title, analysis_title(at))
        self.assertEqual(analysis_title(at), f"**{clean_name(chosen['name'])}** · {type_label(chosen['property_type'])}")
        self.assertIn(clean_name(chosen["name"]), pitch_markdown(at))

    def test_every_property_can_be_chosen_without_errors(self):
        for prop in load_properties():
            at = start_app()
            at.sidebar.selectbox[0].select(clean_name(prop["name"])).run()
            self.assertEqual(len(at.exception), 0, prop["name"])
            self.assertNotIn("Placeholder", everything_displayed(at), prop["name"])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class PitchSectionTests(unittest.TestCase):
    def test_pitch_defaults_to_the_number_one_brand_with_a_download_button(self):
        at = start_app()
        picker = brand_picker(at)
        self.assertIsNotNone(picker.value)
        self.assertTrue(picker.format_func(picker.value).startswith("1. "))
        self.assertIn(picker.format_func(picker.value).split(". ", 1)[1], pitch_markdown(at))
        self.assertEqual(len(at.get("download_button")), 1)

    def test_pitch_shown_on_the_page_has_no_internal_scoring_language(self):
        text = pitch_markdown(start_app())
        for phrase in ("Commercial score", "match score", "/ 100", "rated"):
            self.assertNotIn(phrase, text)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class JointFirstTests(unittest.TestCase):
    """Uses a temporary copy of the data in which a second brand is identical
    to the Premier tournament's top match, creating a joint first."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        for csv_file in (PROJECT / "data").glob("*.csv"):
            shutil.copy(csv_file, self.folder)
        with open(Path(self.folder) / "brands.csv", "a", encoding="utf-8") as file:
            file.write("B99,Placeholder Twin Watchmaker,luxury_watches,UK,Active UK sport sponsor,0,5,25,45,25,TRUE,TRUE\n")
        os.environ["SCOUT_DATA_DIR"] = self.folder
        self.addCleanup(shutil.rmtree, self.folder)
        self.addCleanup(os.environ.pop, "SCOUT_DATA_DIR", None)

    def test_user_must_choose_a_brand_when_two_share_first_place(self):
        at = start_app()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("share first place" in w.value for w in at.warning))
        self.assertIsNone(brand_picker(at).value)  # no default
        self.assertIsNone(pitch_markdown(at))  # no pitch yet
        self.assertEqual(len(at.get("download_button")), 0)

    def test_pitch_appears_once_a_brand_is_chosen(self):
        at = start_app()
        brand_picker(at).select("B99").run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Twin Watchmaker", pitch_markdown(at))
        self.assertNotIn("Placeholder", pitch_markdown(at))
        self.assertEqual(len(at.get("download_button")), 1)

    def test_no_prompt_for_a_property_without_a_joint_first(self):
        at = start_app()
        at.sidebar.selectbox[0].select(clean_name(load_properties()[3]["name"])).run()  # the BUCS team: clear winner
        self.assertFalse(any("share first place" in w.value for w in at.warning))
        self.assertIsNotNone(brand_picker(at).value)


class DataFolderTests(unittest.TestCase):
    def test_data_folder_can_be_overridden_for_tests(self):
        from data_loader import data_dir

        os.environ["SCOUT_DATA_DIR"] = "/somewhere/else"
        try:
            self.assertEqual(str(data_dir()), "/somewhere/else")
        finally:
            del os.environ["SCOUT_DATA_DIR"]
        self.assertEqual(data_dir().name, "data")


if __name__ == "__main__":
    unittest.main()
