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

    def test_placeholder_banner_is_visible(self):
        banners = [w.value for w in start_app().warning]
        self.assertTrue(any("PLACEHOLDER DATA" in text for text in banners))

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
        self.assertTrue(any("PLACEHOLDER DATA" in w.value for w in at.warning))

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
        picker = at.main.selectbox[0]
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
        self.assertIsNone(at.main.selectbox[0].value)  # no default
        self.assertIsNone(pitch_markdown(at))  # no pitch yet
        self.assertEqual(len(at.get("download_button")), 0)

    def test_pitch_appears_once_a_brand_is_chosen(self):
        at = start_app()
        at.main.selectbox[0].select("B99").run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Twin Watchmaker", pitch_markdown(at))
        self.assertNotIn("Placeholder", pitch_markdown(at))
        self.assertEqual(len(at.get("download_button")), 1)

    def test_no_prompt_for_a_property_without_a_joint_first(self):
        at = start_app()
        at.sidebar.selectbox[0].select(clean_name(load_properties()[3]["name"])).run()  # the BUCS team: clear winner
        self.assertFalse(any("share first place" in w.value for w in at.warning))
        self.assertIsNotNone(at.main.selectbox[0].value)


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
