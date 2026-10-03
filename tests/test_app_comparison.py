"""Drives the real app's "Compare like for like" switch the way a person would.
Wikipedia is replaced by stand-ins (see wiki_fixtures.py), so no test uses the internet.

These tests need Streamlit and are skipped if it is not installed. Run them with:
    .venv/bin/python -m unittest discover tests -v
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).parent))

import comparison
import scoring
import test_app_lookup as lookup_tests  # shared helpers and the base class (used by name, not imported into this module)
import wiki_fixtures as fixtures
import wikipedia_lookup as wiki
from data_loader import load_properties
from display import clean_name, property_label

TODAY = date(2026, 10, 3)
TITLES = ["Queen's Club Championships", "Ilkley Trophy", "Toby Samuel"]  # the saved properties that have a page
QUEENS_VIEWS = sum(fixtures.CATALOGUE["Queen's Club Championships"]["views"])  # 123,941 a year
SKIP = unittest.skipIf(lookup_tests.AppTest is None, "Streamlit is not installed")


def fixture_views():
    fetch = fixtures.make_fetch()
    return {title: wiki.page_views(title, fetch, today=TODAY) for title in TITLES}


def expected_scores(extra=()):
    """What the like-for-like scores should be, worked out directly from the scoring code."""
    properties = load_properties() + list(extra)
    converted = comparison.like_for_like(properties, fixture_views())
    return {property_label(p): scoring.score_property(c)["total"] for p, c in zip(properties, converted)}


def standard_scores(extra=()):
    return {property_label(p): scoring.score_property(p)["total"] for p in load_properties() + list(extra)}


def shown_scores(at):
    table = lookup_tests.ranking(at)
    return dict(zip(table["Property"], table["Score"]))


def toggle(at):
    return at.toggle(key="like_for_like")


@SKIP
class SwitchBehaviourTests(lookup_tests.LookupTestCase):
    def pageview_calls(self):
        return [c for c in self.calls if "/metrics/pageviews/" in c]

    def turn_on(self, at=None):
        at = at or self.start()
        toggle(at).set_value(True).run()
        return at

    # --- off by default: nothing changes ---
    def test_the_switch_is_off_by_default(self):
        at = self.start()
        self.assertIs(toggle(at).value, False)
        self.assertIn("Compare like for like", toggle(at).label)

    def test_off_means_the_standard_scores_and_no_wikipedia_requests(self):
        at = self.start()
        self.assertEqual(self.calls, [])
        for name, score in standard_scores().items():
            self.assertAlmostEqual(shown_scores(at)[name], score, places=6)
        self.assertEqual(len(at.info), 0)

    # --- fetching ---
    def test_turning_it_on_fetches_page_views_only_for_properties_that_have_a_page(self):
        self.turn_on()
        calls = self.pageview_calls()
        self.assertEqual(len(calls), 3)
        for title in ("Queen%27s_Club_Championships", "Ilkley_Trophy", "Toby_Samuel"):
            self.assertTrue(any(title in c for c in calls), title)

    def test_the_fetch_is_remembered_so_nothing_is_downloaded_twice(self):
        at = self.turn_on()
        toggle(at).set_value(False).run()
        toggle(at).set_value(True).run()
        at.sidebar.slider[0].set_value(60).run()
        at.sidebar.selectbox(key="property_choice").select("Toby Samuel").run()
        self.assertEqual(len(self.pageview_calls()), 3)

    # --- the scores ---
    def test_on_means_every_property_is_scored_on_page_views(self):
        at = self.turn_on()
        for name, score in expected_scores().items():
            self.assertAlmostEqual(shown_scores(at)[name], score, places=6, msg=name)

    def test_the_ranking_really_changes(self):
        on, off = shown_scores(self.turn_on()), standard_scores()
        self.assertNotEqual({k: round(v, 3) for k, v in on.items()}, {k: round(v, 3) for k, v in off.items()})

    def test_turning_it_off_again_restores_the_standard_scores_exactly(self):
        at = self.turn_on()
        toggle(at).set_value(False).run()
        for name, score in standard_scores().items():
            self.assertAlmostEqual(shown_scores(at)[name], score, places=6, msg=name)

    def test_the_scores_stay_out_of_100(self):
        self.assertTrue(all(0 <= s <= 100 for s in shown_scores(self.turn_on()).values()))

    def test_the_sliders_still_work_in_this_mode(self):
        at = self.turn_on()
        factors = list(scoring.FACTOR_LABELS)  # the sliders are in this order
        at.sidebar.slider[factors.index("audience")].set_value(100)
        for factor in ("engagement", "demographics", "media", "prestige"):
            at.sidebar.slider[factors.index(factor)].set_value(0)
        at.run()
        self.assertEqual(len(at.exception), 0)
        # with only the audience counting, the busiest page wins
        table = lookup_tests.ranking(at)
        self.assertEqual(table.iloc[0]["Property"], "Queen's (HSBC Championships)")

    def test_the_saved_data_files_are_never_changed(self):
        before = {p: p.read_bytes() for p in (PROJECT / "data").glob("*.csv")}
        self.turn_on()
        self.assertEqual(before, {p: p.read_bytes() for p in (PROJECT / "data").glob("*.csv")})

    # --- explaining what is going on ---
    def test_an_explanation_appears_when_it_is_on(self):
        notices = " ".join(i.value for i in self.turn_on().info)
        self.assertIn("Like-for-like mode", notices)
        self.assertIn("Wikipedia page views over the last 12 complete months", notices)
        self.assertIn("no Wikipedia page", notices)
        self.assertIn("The pitch still uses each property's own best figures", notices)

    def test_a_table_shows_each_propertys_audience_on_the_same_measure(self):
        at = self.turn_on()
        table = next(t.value for t in at.dataframe if "Page views a year" in t.value.columns).set_index("Property")
        self.assertEqual(len(table), 5)
        self.assertEqual(table.loc["Queen's (HSBC Championships)", "Page views a year"], f"{QUEENS_VIEWS:,}")
        self.assertEqual(table.loc["Lexus Ilkley Open", "Wikipedia page"], "Ilkley Trophy")
        self.assertEqual(table.loc["Lexus Ilkley Open", "Page views a year"], "4,800")
        self.assertEqual(table.loc["Toby Samuel", "Page views a year"], "12,000")
        for name in ("Lexus British Open Roehampton (ITF J300)", "Queen Mary Tennis Club (BUCS)"):
            self.assertEqual(table.loc[name, "Wikipedia page"], "No Wikipedia page", name)

    def test_the_table_links_every_figure_to_its_source(self):
        at = self.turn_on()
        table = next(t.value for t in at.dataframe if "Page views a year" in t.value.columns).set_index("Property")
        for name in ("Queen's (HSBC Championships)", "Lexus Ilkley Open", "Toby Samuel"):
            self.assertTrue(str(table.loc[name, "Source"]).startswith("https://pageviews.wmcloud.org/"), name)

    def test_the_standard_audience_figure_is_still_shown_for_reference(self):
        at = self.turn_on()
        table = next(t.value for t in at.dataframe if "Page views a year" in t.value.columns).set_index("Property")
        column = "Standard audience figure (not used in this mode)"
        self.assertEqual(table.loc["Queen's (HSBC Championships)", column], "1.8 million people")
        self.assertEqual(table.loc["Toby Samuel", column], "6,369 Instagram followers")

    # --- the analysis of one property ---
    def test_the_analysis_shows_the_page_views_and_the_standard_figure_side_by_side(self):
        table = lookup_tests.breakdown(self.turn_on())
        self.assertEqual(
            table.loc["Audience size", "Figure"],
            f"{QUEENS_VIEWS:,} Wikipedia page views a year (a proxy for public interest) · standard figure: 1.8 million people",
        )
        self.assertEqual(table.loc["Audience size", "Confidence"], "Calculated")

    def test_the_analysis_says_it_is_in_this_mode(self):
        captions = " ".join(c.value for c in self.turn_on().caption)
        self.assertIn("Scored in like-for-like mode", captions)

    def test_a_property_without_a_page_is_not_measured_on_the_audience_and_its_weight_is_shared(self):
        at = self.turn_on()
        at.sidebar.selectbox(key="property_choice").select("Lexus British Open Roehampton (ITF J300)").run()
        table = lookup_tests.breakdown(at)
        self.assertEqual(table.loc["Audience size", "Confidence"], "Not measured")
        self.assertEqual(table.loc["Audience size", "Figure"], "No Wikipedia page views available · standard figure: 3,000 people")
        self.assertEqual(table.loc["Audience size", "Weight"], 0)
        self.assertEqual(table.loc["Audience size", "Weight set"], 25)
        self.assertAlmostEqual(table["Weight"].sum(), 100, places=0)
        self.assertIn("Not measured: Audience size (weight 25), Social engagement (weight 20)", " ".join(i.value for i in at.info))

    def test_a_property_that_has_a_page_keeps_all_its_weights(self):
        at = self.turn_on()
        at.sidebar.selectbox(key="property_choice").select("Toby Samuel").run()
        self.assertNotIn("Weight set", lookup_tests.breakdown(at).columns)  # nothing redistributed

    def test_the_sources_panel_shows_the_page_views_source(self):
        at = self.turn_on()
        sources = next(t.value for t in at.dataframe if list(t.value.columns) == ["Figure", "Source", "Confidence", "Link"])
        self.assertIn("Wikipedia page views", sources.iloc[0]["Source"])
        self.assertTrue(sources.iloc[0]["Link"].startswith("https://pageviews.wmcloud.org/"))

    # --- the pitch is for a brand, so it keeps the property's own best figures ---
    def test_the_pitch_uses_the_real_audience_not_the_comparison_measure(self):
        text = lookup_tests.pitch_text(self.turn_on())
        self.assertIn("Audience reach: 1.8 million people", text)
        self.assertNotIn("Online interest", text)
        self.assertNotIn("page views", text)

    def test_a_player_pitch_keeps_instagram_followers(self):
        at = self.turn_on()
        at.sidebar.selectbox(key="property_choice").select("Toby Samuel").run()
        self.assertIn("Instagram followers: 6,369", lookup_tests.pitch_text(at))

    def test_the_pitch_is_the_same_with_the_switch_on_or_off(self):
        off = lookup_tests.pitch_text(self.start())
        on = lookup_tests.pitch_text(self.turn_on())
        self.assertEqual(on, off)

    # --- the type filter still works ---
    def test_the_type_filter_works_in_this_mode(self):
        at = self.turn_on()
        at.selectbox(key="type_filter").select("premium_tournament").run()
        table = lookup_tests.ranking(at)
        self.assertEqual(list(table["Property"]), ["Queen's (HSBC Championships)"])
        self.assertAlmostEqual(table.iloc[0]["Score"], expected_scores()["Queen's (HSBC Championships)"], places=6)

    def test_nothing_shown_calls_a_name_a_placeholder(self):
        at = self.turn_on()
        shown = " ".join(m.value for m in at.markdown) + " ".join(str(o) for s in at.selectbox for o in s.options)
        self.assertNotIn("Placeholder", shown)
        self.assertEqual(len(at.exception), 0)


@SKIP
class LookupFairnessTests(lookup_tests.LookupTestCase):
    """The reason for the switch: a Wikipedia lookup ranked against the saved properties."""

    def scored_lookup_with_real_attendance(self):
        """Look up Queen's Club Championships but replace the page-view audience with a real attendance figure."""
        at = self.flow(lookup_tests.QUEENS)
        at.checkbox(key=f"wf_views|{lookup_tests.QUEENS}").set_value(False).run()
        prefix = self.prefix(at)
        at.number_input(key=prefix + "audience_value").set_value(5_000_000)
        at.radio(key=prefix + "audience_mode").set_value("Sourced")
        at.text_input(key=prefix + "audience_source").set_value("Attendance plus TV audience (my figures)")
        self.fill_in(at)
        return self.submit(at)

    def lookup_property(self, at):
        return at.session_state["custom_properties"][lookup_tests.QUEENS_LABEL]

    def test_in_standard_mode_the_typed_attendance_is_used(self):
        at = self.scored_lookup_with_real_attendance()
        self.assertIn("5 million people", lookup_tests.breakdown(at).loc["Audience size", "Figure"])

    def test_in_like_for_like_mode_the_lookup_uses_page_views_like_everything_else(self):
        at = self.scored_lookup_with_real_attendance()
        toggle(at).set_value(True).run()
        figure = lookup_tests.breakdown(at).loc["Audience size", "Figure"]
        self.assertTrue(figure.startswith(f"{QUEENS_VIEWS:,} Wikipedia page views a year"))
        self.assertIn("standard figure: 5 million people", figure)

    def test_the_lookup_is_ranked_against_the_saved_properties_on_the_same_measure(self):
        at = self.scored_lookup_with_real_attendance()
        toggle(at).set_value(True).run()
        lookup = self.lookup_property(at)
        expected = expected_scores([lookup])
        shown = shown_scores(at)
        self.assertEqual(set(shown), set(expected))
        for name, score in expected.items():
            self.assertAlmostEqual(shown[name], score, places=6, msg=name)

    def test_the_lookup_and_the_saved_queens_page_get_the_same_audience_score(self):
        # Both are about the same Wikipedia page, so on the same measure they must tie on audience.
        at = self.scored_lookup_with_real_attendance()
        toggle(at).set_value(True).run()
        lookup_audience = lookup_tests.breakdown(at).loc["Audience size", "Score (0-10)"]
        at.sidebar.selectbox(key="property_choice").select("Queen's (HSBC Championships)").run()
        saved_audience = lookup_tests.breakdown(at).loc["Audience size", "Score (0-10)"]
        self.assertEqual(lookup_audience, saved_audience)

    def test_without_the_switch_the_two_would_have_been_ranked_unfairly(self):
        at = self.scored_lookup_with_real_attendance()
        lookup, standard = self.lookup_property(at), None
        standard = scoring.factor_scores(lookup)["audience"]
        on = scoring.factor_scores(comparison.like_for_like([lookup], fixture_views())[0])["audience"]
        self.assertGreater(standard, on)  # a typed 5 million would have beaten the page views

    def test_a_nudge_appears_in_standard_mode_when_a_lookup_uses_page_views(self):
        at = self.flow(lookup_tests.QUEENS)
        self.submit(self.fill_in(at))  # keeps the page-view audience
        captions = " ".join(c.value for c in at.caption)
        self.assertIn("not comparable with the saved properties' attendance and TV figures", captions)
        self.assertIn("Compare like for like", captions)

    def test_the_nudge_goes_away_in_like_for_like_mode(self):
        at = self.flow(lookup_tests.QUEENS)
        self.submit(self.fill_in(at))
        toggle(at).set_value(True).run()
        self.assertNotIn("not comparable with the saved properties", " ".join(c.value for c in at.caption))

    def test_there_is_no_nudge_without_a_lookup(self):
        self.assertNotIn("not comparable with the saved properties", " ".join(c.value for c in self.start().caption))

    def test_there_is_no_nudge_when_the_lookup_uses_a_real_audience_figure(self):
        at = self.scored_lookup_with_real_attendance()
        self.assertNotIn("not comparable with the saved properties", " ".join(c.value for c in at.caption))

    def test_a_lookup_without_a_wikipedia_title_would_have_no_audience_in_this_mode(self):
        # The lookup always records the page it came from, so it can always be compared.
        at = self.scored_lookup_with_real_attendance()
        self.assertEqual(self.lookup_property(at)["wikipedia_title"], lookup_tests.QUEENS)

    def test_removing_the_lookup_removes_it_from_the_like_for_like_ranking_too(self):
        at = self.scored_lookup_with_real_attendance()
        toggle(at).set_value(True).run()
        self.assertEqual(len(lookup_tests.ranking(at)), 6)
        lookup_tests.button(at, "Remove my Wikipedia lookups").click()
        at.run()
        self.assertEqual(len(lookup_tests.ranking(at)), 5)
        self.assertEqual(len(at.exception), 0)


@SKIP
class WikipediaDownTests(unittest.TestCase):
    """If Wikipedia cannot be reached, the app must say so and show the standard scores."""

    def setUp(self):
        self.down = True
        real = fixtures.make_fetch()

        def flaky(url):
            if self.down and "/metrics/pageviews/" in url:
                raise wiki.WikipediaError("Could not reach Wikipedia. Check your internet connection and try again.")
            return real(url)

        patcher = mock.patch.object(wiki, "fetch_json", flaky)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self):
        return lookup_tests.AppTest.from_file(lookup_tests.APP_FILE, default_timeout=30).run()

    def test_the_standard_scores_are_shown_with_a_warning(self):
        at = self.start()
        toggle(at).set_value(True).run()
        self.assertEqual(len(at.exception), 0)
        warnings = " ".join(w.value for w in at.warning)
        self.assertIn("Could not fetch Wikipedia page views, so the standard scores are shown instead.", warnings)
        self.assertIn("Could not reach Wikipedia", warnings)
        for name, score in standard_scores().items():
            self.assertAlmostEqual(shown_scores(at)[name], score, places=6, msg=name)

    def test_the_warning_names_the_pages_that_failed(self):
        at = self.start()
        toggle(at).set_value(True).run()
        warnings = " ".join(w.value for w in at.warning)
        for title in TITLES:
            self.assertIn(title, warnings)

    def test_a_failure_is_not_mistaken_for_no_page(self):
        at = self.start()
        toggle(at).set_value(True).run()
        notices = " ".join(i.value for i in at.info)
        self.assertNotIn("Like-for-like mode", notices)  # it did not switch on with blank audiences
        self.assertEqual(at.session_state["pageview_cache"], {})

    def test_it_recovers_by_itself_once_wikipedia_is_back(self):
        at = self.start()
        toggle(at).set_value(True).run()
        self.down = False
        at.run()
        self.assertIn("Like-for-like mode", " ".join(i.value for i in at.info))
        for name, score in expected_scores().items():
            self.assertAlmostEqual(shown_scores(at)[name], score, places=6, msg=name)

    def test_switching_off_still_works_while_wikipedia_is_down(self):
        at = self.start()
        toggle(at).set_value(True).run()
        toggle(at).set_value(False).run()
        self.assertEqual([w.value for w in at.warning if "Could not fetch" in w.value], [])


if __name__ == "__main__":
    unittest.main()
