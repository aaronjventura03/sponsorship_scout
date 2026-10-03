"""Drives the real app through the Wikipedia lookup, the form, scoring, and the property-type
filter, the way a person would. Wikipedia is replaced by stand-ins (see wiki_fixtures.py), so
no test uses the internet.

These tests need Streamlit and are skipped if it is not installed. Run them with:
    .venv/bin/python -m unittest discover tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Streamlit is not installed in this Python
    AppTest = None

import scoring
import wiki_fixtures as fixtures
import wikipedia_lookup as wiki
from data_loader import load_properties

APP_FILE = str(PROJECT / "app.py")
QUEENS = "Queen's Club Championships"
QUEENS_LABEL = "Queen's Club Championships (Wikipedia lookup)"
QUEENS_YEAR_OF_VIEWS = sum(fixtures.CATALOGUE[QUEENS]["views"])  # the fake page views for a whole year
FORM_BUTTON = "Score this property"
RANKING_COLUMNS = ["Rank", "Property", "Type", "Score"]


def button(at, label):
    return next(b for b in at.button if b.label == label)


def ranking(at):
    """The ranking table (the one with Rank, Property, Type and Score columns)."""
    return next(t.value for t in at.dataframe if list(t.value.columns) == RANKING_COLUMNS)


def breakdown(at):
    return next(t.value for t in at.dataframe if "Weight" in t.value.columns).set_index("Factor")


def gave_us(at):
    """The "What Wikipedia gave us" table."""
    return next(t.value for t in at.dataframe if list(t.value.columns) == ["Figure", "Value", "Source"])


def pitch_text(at):
    return next((m.value for m in at.markdown if "# Partnership opportunity" in m.value), None)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class LookupTestCase(unittest.TestCase):
    """Base class: every test runs with Wikipedia replaced by the stand-in."""

    def setUp(self):
        self.calls = []
        patcher = mock.patch.object(wiki, "fetch_json", fixtures.make_fetch(calls=self.calls))
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- ways of driving the app ---
    def start(self):
        return AppTest.from_file(APP_FILE, default_timeout=30).run()

    def search(self, at, query):
        at.text_input(key="wiki_query").set_value(query)
        button(at, "Search Wikipedia").click()
        return at.run()

    def use_first_page(self, at):
        button(at, "Use this page").click()
        return at.run()

    def flow(self, query=QUEENS):
        """Search for a name and use the top result. Returns the app."""
        at = self.start()
        self.search(at, query)
        return self.use_first_page(at)

    def prefix(self, at):
        return at.session_state["wiki_form_prefix"]

    def number(self, at, name):
        return at.number_input(key=self.prefix(at) + name)

    def fill_in(self, at, prestige=9, broadcast=9, income=40.0):
        self.number(at, "prestige_value").set_value(prestige)
        self.number(at, "media_value").set_value(broadcast)
        self.number(at, "demographics_value").set_value(income)
        return at

    def submit(self, at):
        button(at, FORM_BUTTON).click()
        return at.run()


class SearchTests(LookupTestCase):
    def test_the_idle_app_makes_no_wikipedia_requests(self):
        at = self.start()
        self.assertEqual(self.calls, [])
        self.assertEqual(len(at.exception), 0)

    def test_a_search_makes_exactly_one_request_and_lists_the_matches(self):
        at = self.start()
        self.search(at, "tennis")
        self.assertEqual(len(self.calls), 1)
        picker = at.selectbox(key="wiki_pick")
        self.assertEqual(picker.options, [
            "Queen's Club Championships: London tennis tournament",
            "Toby Samuel: British tennis player (born 2002)",
        ])

    def test_nothing_else_is_fetched_until_a_page_is_chosen(self):
        at = self.start()
        self.search(at, "tennis")
        self.assertEqual(len(self.calls), 1)
        at.run()  # a plain re-run (as happens whenever anything is clicked)
        self.assertEqual(len(self.calls), 1)

    def test_a_blank_search_gives_a_friendly_message(self):
        at = self.start()
        button(at, "Search Wikipedia").click()
        at.run()
        self.assertEqual([e.value for e in at.error], ["Type a tournament or player name to search for."])
        self.assertEqual(self.calls, [])

    def test_a_search_with_no_matches_says_so(self):
        at = self.start()
        self.search(at, "zzz nothing")
        self.assertTrue(any("No Wikipedia pages matched" in w.value for w in at.warning))
        self.assertEqual(len(at.exception), 0)

    def test_a_new_search_replaces_the_old_results_and_page(self):
        at = self.flow(QUEENS)
        self.assertIsNotNone(at.session_state["wiki_page"])
        self.search(at, "toby samuel")
        self.assertIsNone(at.session_state["wiki_page"])
        self.assertEqual(at.selectbox(key="wiki_pick").options, ["Toby Samuel: British tennis player (born 2002)"])


class FetchedDataTests(LookupTestCase):
    def test_using_a_page_makes_three_more_requests(self):
        self.flow()
        self.assertEqual(len(self.calls), 1 + 3)  # search, then summary, info box and page views

    def test_the_summary_and_licence_are_shown_with_a_source_link(self):
        at = self.flow()
        text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
        self.assertIn("annual professional tennis tournament", text)
        self.assertIn("https://en.wikipedia.org/wiki/Queen's_Club_Championships", text)
        self.assertIn("CC BY-SA 4.0", text)
        self.assertIn("creativecommons.org", text)

    def test_every_fetched_figure_has_a_source_link(self):
        table = gave_us(self.flow())
        self.assertGreaterEqual(len(table), 8)
        for _, row in table.iterrows():
            self.assertTrue(str(row["Source"]).startswith("https://"), row["Figure"])

    def test_the_sources_are_the_right_ones(self):
        table = gave_us(self.flow()).set_index("Figure")
        self.assertEqual(table.loc["Page summary", "Source"], "https://en.wikipedia.org/wiki/Queen's_Club_Championships")
        self.assertTrue(table.loc["Monthly page views (12-month average)", "Source"].startswith("https://pageviews.wmcloud.org/"))
        self.assertEqual(table.loc["Surface", "Source"], "https://en.wikipedia.org/wiki/Queen's_Club_Championships")

    def test_the_page_view_figures_are_correct(self):
        table = gave_us(self.flow()).set_index("Figure")
        self.assertEqual(table.loc["Monthly page views (12-month average)", "Value"], f"{round(QUEENS_YEAR_OF_VIEWS / 12):,}")
        self.assertEqual(table.loc["Page views in a year (average x 12)", "Value"], f"{QUEENS_YEAR_OF_VIEWS:,}")

    def test_useful_facts_from_the_info_box_are_listed(self):
        table = gave_us(self.flow()).set_index("Figure")
        self.assertEqual(table.loc["City", "Value"], "London")
        self.assertEqual(table.loc["Surface", "Value"], "Grass / outdoors")
        self.assertEqual(table.loc["ATP prize money", "Value"], "€2,583,330 (2026)")

    def test_a_monthly_page_view_chart_is_shown(self):
        at = self.flow()
        self.assertEqual(len(at.get("vega_lite_chart")), 1)  # st.bar_chart
        self.assertTrue(any("last 12 complete months" in c.value for c in at.caption))

    def test_a_player_page_gets_player_facts(self):
        table = gave_us(self.flow("toby samuel")).set_index("Figure")
        self.assertEqual(table.loc["Born", "Value"], "6 September 2002")
        self.assertEqual(table.loc["Current singles ranking", "Value"], "No. 98 (21 September 2026)")

    def test_a_disambiguation_page_explains_and_offers_no_form(self):
        at = self.flow("mercury")
        self.assertTrue(any("disambiguation page" in w.value for w in at.warning))
        self.assertNotIn(FORM_BUTTON, [b.label for b in at.button])

    def test_a_page_with_no_extras_says_what_is_missing(self):
        at = self.flow("tiny club")
        warnings = " ".join(w.value for w in at.warning)
        self.assertIn("no info box", warnings)
        self.assertIn("no page-view data", warnings)

    def test_wikipedia_being_unreachable_shows_a_message_and_the_app_keeps_working(self):
        down = mock.patch.object(wiki, "fetch_json", side_effect=wiki.WikipediaError("Could not reach Wikipedia. Check your internet connection and try again."))
        down.start()
        self.addCleanup(down.stop)
        at = self.start()
        self.search(at, "queen's club championships")
        self.assertEqual([e.value for e in at.error], ["Could not reach Wikipedia. Check your internet connection and try again."])
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(ranking(at)), 5)  # the saved properties are still there


class FormTests(LookupTestCase):
    def test_the_form_starts_with_what_wikipedia_gave_us(self):
        at = self.flow()
        self.assertEqual(at.selectbox(key=f"wf_type|{QUEENS}").value, "premium_tournament")  # suggested
        self.assertEqual(at.text_input(key=self.prefix(at) + "name").value, QUEENS)
        self.assertEqual(self.number(at, "audience_value").value, QUEENS_YEAR_OF_VIEWS)

    def test_the_page_view_audience_is_marked_sourced_with_its_source_and_link(self):
        at = self.flow()
        prefix = self.prefix(at)
        self.assertEqual(at.radio(key=prefix + "audience_mode").value, "Sourced")
        self.assertIn("Wikipedia page views", at.text_input(key=prefix + "audience_source").value)
        self.assertTrue(at.text_input(key=prefix + "audience_url").value.startswith("https://pageviews.wmcloud.org/"))

    def test_figures_wikipedia_does_not_have_start_blank_and_estimated(self):
        at = self.flow()
        for name in ("engagement", "demographics", "media", "prestige"):
            self.assertIsNone(self.number(at, f"{name}_value").value, name)
            self.assertEqual(at.radio(key=self.prefix(at) + f"{name}_mode").value, "Estimated", name)

    def test_unticking_page_views_blanks_the_audience(self):
        at = self.flow()
        at.checkbox(key=f"wf_views|{QUEENS}").set_value(False).run()
        self.assertIsNone(self.number(at, "audience_value").value)
        self.assertEqual(at.radio(key=self.prefix(at) + "audience_mode").value, "Estimated")

    def test_changing_the_type_refreshes_the_starting_age_profile(self):
        at = self.flow()
        self.assertEqual(self.number(at, "age_18_24").value, 12)  # the premium default
        at.selectbox(key=f"wf_type|{QUEENS}").select("university_team").run()
        self.assertEqual(self.number(at, "age_18_24").value, 85)
        self.assertFalse(at.checkbox(key=self.prefix(at) + "minors").value)
        at.selectbox(key=f"wf_type|{QUEENS}").select("junior_event").run()
        self.assertTrue(at.checkbox(key=self.prefix(at) + "minors").value)  # junior events include children

    def test_a_page_with_no_clear_type_asks_for_one_first(self):
        at = self.flow("tiny club")
        self.assertIn("Choose a property type to continue.", [c.value for c in at.caption])
        self.assertNotIn(FORM_BUTTON, [b.label for b in at.button])
        at.selectbox(key="wf_type|Tiny Club").select("player").run()
        self.assertIn(FORM_BUTTON, [b.label for b in at.button])

    def test_the_form_asks_for_sourced_or_estimated_on_every_figure(self):
        at = self.flow()
        names = {r.key.split("|")[-1] for r in at.radio if r.key.startswith("wf|")}
        self.assertEqual(names, {"audience_mode", "engagement_mode", "demographics_mode", "media_mode", "prestige_mode", "age_mode"})


class ScoringFromTheFormTests(LookupTestCase):
    def scored(self, **kwargs):
        return self.submit(self.fill_in(self.flow(), **kwargs))

    def test_scoring_adds_the_property_and_selects_it(self):
        at = self.scored()
        self.assertEqual(len(at.exception), 0)
        self.assertIn(QUEENS_LABEL, at.session_state["custom_properties"])
        self.assertEqual(at.sidebar.selectbox(key="property_choice").value, QUEENS_LABEL)
        self.assertTrue(any("Scored." in s.value for s in at.success))

    def test_it_joins_the_ranking(self):
        at = self.scored()
        table = ranking(at)
        self.assertEqual(len(table), 6)
        self.assertIn(QUEENS_LABEL, list(table["Property"]))
        scores = list(table["Score"])
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_the_analysis_uses_the_existing_scoring(self):
        at = self.scored()
        prop = at.session_state["custom_properties"][QUEENS_LABEL]
        self.assertAlmostEqual(float(at.metric[0].value), scoring.score_property(prop)["total"], delta=0.06)

    def test_each_figure_is_marked_by_how_it_was_obtained(self):
        table = breakdown(self.scored())
        self.assertEqual(table.loc["Audience size", "Confidence"], "Calculated")   # from page views
        self.assertEqual(table.loc["Purchasing power", "Confidence"], "Estimate")
        self.assertEqual(table.loc["Broadcast exposure", "Confidence"], "Estimate")
        self.assertEqual(table.loc["Prestige", "Confidence"], "Estimate")

    def test_the_audience_is_described_as_page_views_not_people(self):
        figure = breakdown(self.scored()).loc["Audience size", "Figure"]
        self.assertEqual(figure, f"{QUEENS_YEAR_OF_VIEWS:,} Wikipedia page views a year (a proxy for public interest)")

    def test_a_blank_figure_is_not_measured_and_its_weight_is_shared(self):
        at = self.scored()  # engagement was left blank
        table = breakdown(at)
        self.assertEqual(table.loc["Social engagement", "Confidence"], "Not measured")
        self.assertEqual(table.loc["Social engagement", "Figure"], "Not provided")
        self.assertEqual(table.loc["Social engagement", "Weight"], 0)
        self.assertAlmostEqual(table["Weight"].sum(), 100, places=0)
        notices = " ".join(i.value for i in at.info)
        self.assertIn("Not measured: Social engagement", notices)

    def test_the_analysis_says_this_came_from_a_lookup_and_is_not_saved(self):
        notices = " ".join(i.value for i in self.scored().info)
        self.assertIn("comes from a Wikipedia lookup plus your own entries", notices)
        self.assertIn("not saved to any file", notices)

    def test_the_sources_panel_lists_where_each_figure_came_from(self):
        at = self.scored()
        sources = next(t.value for t in at.dataframe if list(t.value.columns) == ["Figure", "Source", "Confidence", "Link"])
        audience = sources.iloc[0]
        self.assertIn("Wikipedia page views", audience["Source"])
        self.assertTrue(audience["Link"].startswith("https://pageviews.wmcloud.org/"))
        self.assertEqual(sources.iloc[-1]["Figure"], "Audience age profile (used in matching)")
        self.assertEqual(sources.iloc[-1]["Confidence"], "Estimate")

    def test_brand_matches_and_a_pitch_are_produced(self):
        at = self.scored()
        self.assertTrue(any("match score" in m.value for m in at.markdown))
        text = pitch_text(at)
        self.assertIn("Queen's Club Championships ×", text)
        self.assertIn("Online interest: 123,941 Wikipedia page views a year", text)
        self.assertIn("Prepared by", text)
        self.assertNotIn("Placeholder", text)
        self.assertEqual(len(at.get("download_button")), 1)

    def test_the_pitch_does_not_present_estimates_as_facts(self):
        text = pitch_text(self.scored())
        self.assertIn("An estimated 40% of the audience is in higher-income brackets", text)  # not "40.0%"
        self.assertIn("likely", text)  # the age profile is an estimate

    def test_the_audience_age_profile_is_flagged_as_an_estimate_next_to_the_matches(self):
        captions = " ".join(c.value for c in self.scored().caption)
        self.assertIn("audience age profile, which is currently an estimate", captions)

    def test_a_source_the_user_gives_is_recorded(self):
        at = self.fill_in(self.flow())
        prefix = self.prefix(at)
        at.radio(key=prefix + "prestige_mode").set_value("Sourced")
        at.text_input(key=prefix + "prestige_source").set_value("ATP: an ATP 500 event")
        at.text_input(key=prefix + "prestige_url").set_value("https://www.atptour.com/")
        self.submit(at)
        prop = at.session_state["custom_properties"][QUEENS_LABEL]
        self.assertEqual(prop["prestige_confidence"], "published")
        self.assertEqual(prop["prestige_source"], "ATP: an ATP 500 event")
        self.assertEqual(prop["prestige_source_url"], "https://www.atptour.com/")

    def test_a_player_lookup_works_too(self):
        at = self.flow("toby samuel")
        self.assertEqual(at.selectbox(key="wf_type|Toby Samuel").value, "player")
        prefix = self.prefix(at)
        at.number_input(key=prefix + "engagement_value").set_value(878)
        at.radio(key=prefix + "engagement_mode").set_value("Sourced")
        at.text_input(key=prefix + "engagement_source").set_value("Median of 10 posts, 2 Oct 2026")
        at.number_input(key=prefix + "rate").set_value(13.8)
        self.submit(at)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.sidebar.selectbox(key="property_choice").value, "Toby Samuel (Wikipedia lookup)")
        self.assertEqual(breakdown(at).loc["Social engagement", "Confidence"], "Published")
        self.assertIn("878 per post", breakdown(at).loc["Social engagement", "Figure"])

    def test_a_property_with_no_figures_at_all_still_scores_without_crashing(self):
        at = self.flow("tiny club")
        at.selectbox(key="wf_type|Tiny Club").select("player").run()
        self.submit(at)
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Tiny Club (Wikipedia lookup)", at.session_state["custom_properties"])
        self.assertEqual(float(at.metric[0].value), 0.0)
        text = pitch_text(at)
        for bad in ("None", "nan"):
            self.assertNotIn(bad, text)

    def test_the_lookup_is_never_written_to_the_csv_files(self):
        before = {p: p.read_bytes() for p in (PROJECT / "data").glob("*.csv")}
        self.scored()
        after = {p: p.read_bytes() for p in (PROJECT / "data").glob("*.csv")}
        self.assertEqual(before, after)

    def test_nothing_displayed_calls_a_name_a_placeholder(self):
        at = self.scored()
        shown = " ".join(m.value for m in at.markdown) + " ".join(str(o) for s in at.selectbox for o in s.options)
        self.assertNotIn("Placeholder", shown)


class FormValidationTests(LookupTestCase):
    def test_a_sourced_figure_without_a_source_is_rejected_and_nothing_is_scored(self):
        at = self.fill_in(self.flow())
        at.radio(key=self.prefix(at) + "prestige_mode").set_value("Sourced")  # but no source note
        self.submit(at)
        self.assertEqual([e.value for e in at.error], ["Prestige (1 to 10): add a source, or mark it as Estimated."])
        self.assertNotIn("custom_properties", at.session_state)
        self.assertEqual(len(ranking(at)), 5)
        self.assertEqual(at.sidebar.selectbox(key="property_choice").value, "Queen's (HSBC Championships)")

    def test_age_groups_that_do_not_total_100_are_rejected(self):
        at = self.fill_in(self.flow())
        self.number(at, "age_35_54").set_value(36)
        self.submit(at)
        self.assertEqual([e.value for e in at.error], ["The audience age groups must total 100 (they total 101)."])

    def test_several_problems_are_all_reported_together(self):
        at = self.fill_in(self.flow())
        prefix = self.prefix(at)
        at.radio(key=prefix + "prestige_mode").set_value("Sourced")
        at.radio(key=prefix + "media_mode").set_value("Sourced")
        self.number(at, "age_35_54").set_value(50)
        self.submit(at)
        self.assertEqual(len(at.error), 3)

    def test_fixing_the_problem_and_resubmitting_works(self):
        at = self.fill_in(self.flow())
        at.radio(key=self.prefix(at) + "prestige_mode").set_value("Sourced")
        self.submit(at)
        self.assertTrue(at.error)
        at.text_input(key=self.prefix(at) + "prestige_source").set_value("ATP")
        self.submit(at)
        self.assertEqual(len(at.error), 0)
        self.assertIn(QUEENS_LABEL, at.session_state["custom_properties"])


class RemovingLookupsTests(LookupTestCase):
    def test_removing_lookups_restores_the_saved_properties_only(self):
        at = self.submit(self.fill_in(self.flow()))
        self.assertEqual(len(ranking(at)), 6)
        button(at, "Remove my Wikipedia lookups").click()
        at.run()
        self.assertEqual(len(ranking(at)), 5)
        self.assertEqual(at.sidebar.selectbox(key="property_choice").value, "Queen's (HSBC Championships)")
        self.assertNotIn("Remove my Wikipedia lookups", [b.label for b in at.button])

    def test_the_remove_button_only_appears_once_there_is_a_lookup(self):
        self.assertNotIn("Remove my Wikipedia lookups", [b.label for b in self.start().button])

    def test_several_lookups_can_sit_side_by_side(self):
        at = self.submit(self.fill_in(self.flow(QUEENS)))
        self.search(at, "toby samuel")
        self.use_first_page(at)
        self.submit(self.fill_in(at))
        self.assertEqual(set(at.session_state["custom_properties"]), {QUEENS_LABEL, "Toby Samuel (Wikipedia lookup)"})
        self.assertEqual(len(ranking(at)), 7)


class TypeFilterTests(LookupTestCase):
    def filter_to(self, at, kind):
        at.selectbox(key="type_filter").select(kind).run()
        return at

    def test_the_filter_lists_all_types_then_each_type_present(self):
        box = self.start().selectbox(key="type_filter")
        self.assertEqual(box.options, ["All types", "Premium tournament", "Challenger tournament", "Junior event", "University team", "Player"])
        self.assertEqual(box.value, "All types")

    def test_all_types_shows_every_property(self):
        self.assertEqual(len(ranking(self.start())), 5)

    def test_each_type_shows_only_its_own_properties(self):
        expected = {p["property_type"]: p["name"] for p in load_properties()}
        for kind, name in expected.items():
            table = ranking(self.filter_to(self.start(), kind))
            self.assertEqual(list(table["Property"]), [name], kind)
            self.assertEqual(list(table["Type"]), [kind.replace("_", " ").capitalize()], kind)

    def test_ranks_count_within_the_chosen_type(self):
        for kind in ("player", "junior_event", "university_team"):
            self.assertEqual(list(ranking(self.filter_to(self.start(), kind))["Rank"]), ["1"], kind)

    def test_a_caption_says_what_is_being_shown(self):
        at = self.filter_to(self.start(), "player")
        self.assertIn("Showing player properties only (1). Ranks count within this type.", [c.value for c in at.caption])
        at = self.filter_to(at, "All types")
        self.assertFalse(any("properties only" in c.value for c in at.caption))

    def test_going_back_to_all_types_restores_the_full_ranking(self):
        at = self.filter_to(self.start(), "player")
        self.assertEqual(len(ranking(at)), 1)
        self.assertEqual(len(ranking(self.filter_to(at, "All types"))), 5)

    def test_the_filter_does_not_change_the_chosen_property_or_its_analysis(self):
        at = self.filter_to(self.start(), "player")  # Queen's is chosen, and is not a player
        self.assertEqual(at.sidebar.selectbox[0].value, "Queen's (HSBC Championships)")
        self.assertTrue(any(m.value.startswith("**Queen's (HSBC Championships)**") for m in at.markdown))
        self.assertEqual(len(at.exception), 0)

    def test_the_filter_follows_the_sliders(self):
        at = self.filter_to(self.start(), "premium_tournament")
        at.sidebar.slider[0].set_value(100).run()
        self.assertEqual(len(ranking(at)), 1)
        self.assertEqual(len(at.exception), 0)

    def test_a_lookup_joins_the_ranking_of_its_own_type_only(self):
        at = self.submit(self.fill_in(self.flow()))  # a premium tournament
        premium = ranking(self.filter_to(at, "premium_tournament"))
        self.assertEqual(len(premium), 2)
        self.assertIn(QUEENS_LABEL, list(premium["Property"]))
        self.assertEqual(list(premium["Rank"]), ["1", "2"])
        self.assertEqual(len(ranking(self.filter_to(at, "player"))), 1)  # unaffected

    def test_a_lookup_of_a_new_type_still_appears_under_that_type(self):
        at = self.flow("tiny club")
        at.selectbox(key="wf_type|Tiny Club").select("university_team").run()
        self.submit(at)
        table = ranking(self.filter_to(at, "university_team"))
        self.assertEqual(len(table), 2)
        self.assertIn("Tiny Club (Wikipedia lookup)", list(table["Property"]))

    def test_removing_the_only_lookup_of_a_type_does_not_leave_a_stale_filter(self):
        # A scenario where the only property of a type is a lookup: the saved data has no player.
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        for csv_file in (PROJECT / "data").glob("*.csv"):
            shutil.copy(csv_file, folder)
        path = Path(folder) / "properties.csv"
        path.write_text("".join(line for line in path.read_text().splitlines(keepends=True) if not line.startswith("P05,")))
        os.environ["SCOUT_DATA_DIR"] = folder
        self.addCleanup(os.environ.pop, "SCOUT_DATA_DIR", None)

        at = self.start()
        self.assertNotIn("Player", at.selectbox(key="type_filter").options)
        self.search(at, "toby samuel")
        self.use_first_page(at)
        self.submit(self.fill_in(at))
        self.assertIn("Player", at.selectbox(key="type_filter").options)  # the lookup brings its type with it
        self.filter_to(at, "player")
        self.assertEqual(list(ranking(at)["Property"]), ["Toby Samuel (Wikipedia lookup)"])

        button(at, "Remove my Wikipedia lookups").click()
        at.run()  # the "player" filter no longer matches anything, and must not break the page
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.selectbox(key="type_filter").value, "All types")
        self.assertEqual(len(ranking(at)), 4)

    def test_every_filter_choice_runs_without_errors_and_keeps_scores_in_range(self):
        for kind in self.start().selectbox(key="type_filter").options[1:]:
            raw = kind.lower().replace(" ", "_")
            at = self.filter_to(self.start(), raw)
            self.assertEqual(len(at.exception), 0, kind)
            self.assertTrue(all(0 <= s <= 100 for s in ranking(at)["Score"]), kind)


if __name__ == "__main__":
    unittest.main()
