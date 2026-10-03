"""Checks the Wikipedia lookup code. No test here uses the internet: every one passes in a
stand-in for the downloader (see wiki_fixtures.py), and a guard fails any test that
accidentally reaches for the real one.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import io
import json
import ssl
import sys
import unittest
import urllib.error
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import wiki_fixtures as fixtures
import wikipedia_lookup as wiki


class NoInternetTestCase(unittest.TestCase):
    """Base class: fails loudly if a test tries to use the real internet."""

    def setUp(self):
        guard = mock.patch.object(wiki, "fetch_json", side_effect=AssertionError("a test reached for the real internet"))
        guard.start()
        self.addCleanup(guard.stop)
        urlopen = mock.patch("urllib.request.urlopen", side_effect=AssertionError("a test reached for the real internet"))
        urlopen.start()
        self.addCleanup(urlopen.stop)


class AddressTests(NoInternetTestCase):
    def test_titles_are_encoded_for_web_addresses(self):
        self.assertEqual(wiki.encode_title("Queen's Club Championships"), "Queen%27s_Club_Championships")
        self.assertEqual(wiki.encode_title("Toby Samuel"), "Toby_Samuel")
        self.assertEqual(wiki.encode_title("Davis Cup (tennis)"), "Davis_Cup_%28tennis%29")

    def test_the_source_link_for_a_page_is_a_normal_wikipedia_address(self):
        self.assertEqual(wiki.page_url("Queen's Club Championships"), "https://en.wikipedia.org/wiki/Queen's_Club_Championships")
        self.assertEqual(wiki.page_url("Toby Samuel"), "https://en.wikipedia.org/wiki/Toby_Samuel")

    def test_the_licence_details_are_available_for_attribution(self):
        self.assertEqual(wiki.LICENCE_NAME, "CC BY-SA 4.0")
        self.assertTrue(wiki.LICENCE_URL.startswith("https://creativecommons.org/"))


class SearchTests(NoInternetTestCase):
    def test_returns_matching_pages_with_descriptions_and_source_links(self):
        results = wiki.search("Queen's Club Championships", fixtures.make_fetch())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Queen's Club Championships")
        self.assertEqual(results[0]["description"], "London tennis tournament")
        self.assertEqual(results[0]["url"], "https://en.wikipedia.org/wiki/Queen's_Club_Championships")

    def test_the_search_term_is_encoded_in_the_request(self):
        calls = []
        wiki.search("Queen's Club Championships", fixtures.make_fetch(calls=calls))
        self.assertEqual(len(calls), 1)
        self.assertIn("q=Queen%27s%20Club%20Championships", calls[0])
        self.assertIn("limit=5", calls[0])

    def test_html_in_the_excerpt_is_removed(self):
        excerpt = wiki.search("Toby Samuel", fixtures.make_fetch())[0]["excerpt"]
        self.assertNotIn("<", excerpt)
        self.assertIn("&", excerpt)  # the &amp; was turned back into a plain ampersand

    def test_a_search_with_no_matches_gives_an_empty_list(self):
        self.assertEqual(wiki.search("zzz nothing", fixtures.make_fetch()), [])

    def test_an_empty_search_is_rejected_with_a_friendly_message(self):
        for blank in ("", "   ", None):
            with self.assertRaises(wiki.WikipediaError) as caught:
                wiki.search(blank, fixtures.make_fetch())
            self.assertIn("Type a tournament or player name", str(caught.exception))

    def test_several_matches_keep_their_order(self):
        titles = [r["title"] for r in wiki.search("tennis", fixtures.make_fetch())]
        self.assertEqual(titles, ["Queen's Club Championships", "Toby Samuel"])


class SummaryTests(NoInternetTestCase):
    def test_reads_the_description_extract_and_link(self):
        page = wiki.summary("Queen's Club Championships", fixtures.make_fetch())
        self.assertEqual(page["title"], "Queen's Club Championships")
        self.assertEqual(page["description"], "London tennis tournament")
        self.assertIn("annual professional tennis tournament", page["extract"])
        self.assertEqual(page["url"], "https://en.wikipedia.org/wiki/Queen's_Club_Championships")
        self.assertEqual(page["type"], "standard")

    def test_a_disambiguation_page_is_recognised(self):
        self.assertEqual(wiki.summary("Mercury", fixtures.make_fetch())["type"], "disambiguation")

    def test_a_missing_page_raises_not_found(self):
        with self.assertRaises(wiki.NotFound):
            wiki.summary("No Such Page", fixtures.make_fetch())

    def test_a_missing_link_falls_back_to_a_built_address(self):
        reply = {"title": "Toby Samuel", "extract": "x"}
        page = wiki.summary("Toby Samuel", lambda url: reply)
        self.assertEqual(page["url"], "https://en.wikipedia.org/wiki/Toby_Samuel")
        self.assertEqual(page["description"], "")


class PageViewTests(NoInternetTestCase):
    def test_the_window_is_the_last_12_complete_months(self):
        self.assertEqual(wiki._month_window(date(2026, 10, 3), 12), (date(2025, 10, 1), date(2026, 9, 30)))

    def test_the_window_crosses_a_year_boundary(self):
        self.assertEqual(wiki._month_window(date(2026, 1, 15), 12), (date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual(wiki._month_window(date(2026, 3, 1), 12), (date(2025, 3, 1), date(2026, 2, 28)))

    def test_the_current_incomplete_month_is_excluded(self):
        start, end = wiki._month_window(date(2026, 10, 31), 12)
        self.assertEqual(end, date(2026, 9, 30))

    def test_the_request_asks_for_monthly_views_by_people_over_that_window(self):
        calls = []
        wiki.page_views("Queen's Club Championships", fixtures.make_fetch(calls=calls), today=date(2026, 10, 3))
        self.assertIn("/all-access/user/Queen%27s_Club_Championships/monthly/20251001/20260930", calls[0])

    def test_averages_and_annual_estimate(self):
        views = wiki.page_views("Toby Samuel", fixtures.make_fetch(), today=date(2026, 10, 3))
        self.assertEqual(len(views["months"]), 12)
        self.assertEqual(views["average_monthly"], 1_000)
        self.assertEqual(views["annual_estimate"], 12_000)

    def test_a_busy_month_lifts_the_average(self):
        views = wiki.page_views("Queen's Club Championships", fixtures.make_fetch(), today=date(2026, 10, 3))
        data = fixtures.CATALOGUE["Queen's Club Championships"]["views"]
        self.assertEqual(views["average_monthly"], round(sum(data) / 12))
        self.assertEqual(views["annual_estimate"], round(sum(data) / 12 * 12))

    def test_months_are_labelled_and_sorted_oldest_first(self):
        views = wiki.page_views("Toby Samuel", fixtures.make_fetch(), today=date(2026, 10, 3))
        self.assertEqual(views["months"][0]["month"], "2025-10")
        self.assertEqual(views["months"][-1]["month"], "2026-09")
        scrambled = lambda url: {"items": list(reversed(fixtures.pageview_items("X", [1, 2, 3])))}
        months = [m["month"] for m in wiki.page_views("X", scrambled, today=date(2026, 10, 3))["months"]]
        self.assertEqual(months, sorted(months))
        self.assertEqual(months, ["2025-10", "2025-11", "2025-12"])

    def test_two_source_links_are_provided(self):
        views = wiki.page_views("Toby Samuel", fixtures.make_fetch(), today=date(2026, 10, 3))
        self.assertTrue(views["source_url"].startswith("https://pageviews.wmcloud.org/"))
        self.assertIn("pages=Toby_Samuel", views["source_url"])
        self.assertTrue(views["api_url"].startswith("https://wikimedia.org/api/rest_v1/metrics/pageviews/"))

    def test_no_data_means_none_not_a_crash(self):
        self.assertIsNone(wiki.page_views("Tiny Club", fixtures.make_fetch()))  # the service says 404
        self.assertIsNone(wiki.page_views("X", lambda url: {"items": []}))

    def test_a_shorter_history_is_averaged_over_the_months_it_has(self):
        short = lambda url: {"items": fixtures.pageview_items("New_Page", [100, 300])}
        views = wiki.page_views("New Page", short, today=date(2026, 10, 3))
        self.assertEqual(views["average_monthly"], 200)
        self.assertEqual(len(views["months"]), 2)


class CleaningTests(NoInternetTestCase):
    def test_links_become_their_text(self):
        self.assertEqual(wiki.clean_wikitext("[[The Queen's Club]]"), "The Queen's Club")
        self.assertEqual(wiki.clean_wikitext("[[Grass court|Grass]] / outdoors"), "Grass / outdoors")

    def test_references_and_comments_are_removed(self):
        self.assertEqual(wiki.clean_wikitext("US $648,325<ref name=\"atp\">{{cite web|url=https://x}}</ref>"), "US $648,325")
        self.assertEqual(wiki.clean_wikitext("12<ref name=a />"), "12")
        self.assertEqual(wiki.clean_wikitext("Value<!-- hidden note -->"), "Value")

    def test_line_breaks_become_commas(self):
        self.assertEqual(wiki.clean_wikitext("A<br />B<br>C"), "A, B, C")

    def test_dates_are_written_out(self):
        self.assertEqual(wiki.clean_wikitext("{{start date and age|df=yes|1886}}"), "1886")
        self.assertEqual(wiki.clean_wikitext("{{birth date and age|2002|9|6|df=y}}"), "6 September 2002")
        self.assertEqual(wiki.clean_wikitext("{{start date|2015|6}}"), "June 2015")

    def test_other_templates(self):
        self.assertEqual(wiki.clean_wikitext("{{convert|1.91|m|abbr=on}}"), "1.91 m")
        self.assertEqual(wiki.clean_wikitext("{{URL|https://www.queensclub.co.uk/|queensclub.co.uk}}"), "queensclub.co.uk")
        self.assertEqual(wiki.clean_wikitext("{{flagicon|GBR}} Great Britain"), "Great Britain")
        self.assertEqual(wiki.clean_wikitext("{{nowrap|No. 98}}"), "No. 98")
        self.assertEqual(wiki.clean_wikitext("{{plainlist|\n* One\n* Two\n}}"), "One, Two")
        self.assertEqual(wiki.clean_wikitext("{{unknown thing|abc}}"), "")

    def test_formatting_marks_are_removed(self):
        self.assertEqual(wiki.clean_wikitext("'''Bold''' and ''italic''"), "Bold and italic")
        self.assertEqual(wiki.clean_wikitext("A&nbsp;B &amp; C"), "A B & C")

    def test_nested_templates_and_links_together(self):
        self.assertEqual(wiki.clean_wikitext("{{nowrap|[[Bath, Somerset|Bath]], England}}"), "Bath, England")

    def test_file_links_are_dropped(self):
        self.assertEqual(wiki.clean_wikitext("[[File:Logo.png|thumb]]Text"), "Text")


class InfoboxTests(NoInternetTestCase):
    def test_a_tournament_info_box_is_read(self):
        kind, fields = wiki.parse_infobox(fixtures.QUEENS_WIKITEXT)
        self.assertEqual(kind, "tennis tournament")
        self.assertEqual(fields["city"], "London")
        self.assertEqual(fields["venue"], "The Queen's Club")
        self.assertEqual(fields["surface"], "Grass / outdoors")
        self.assertEqual(fields["founded"], "1886")
        self.assertEqual(fields["atpprizemoney"], "€2,583,330 (2026)")
        self.assertEqual(fields["website"], "queensclub.co.uk")

    def test_field_names_are_simplified(self):
        _, fields = wiki.parse_infobox(fixtures.QUEENS_WIKITEXT)
        self.assertIn("atpcategory", fields)  # was "ATP category"
        self.assertIn("wtatier", fields)      # was "WTA tier" with no spaces around the bar

    def test_a_player_info_box_is_read(self):
        kind, fields = wiki.parse_infobox(fixtures.TOBY_WIKITEXT)
        self.assertEqual(kind, "tennis biography")
        self.assertEqual(fields["birthdate"], "6 September 2002")
        self.assertEqual(fields["height"], "1.91 m")
        self.assertEqual(fields["careerprizemoney"], "US $648,325")
        self.assertEqual(fields["countryrepresented"], "Great Britain")
        self.assertEqual(fields["currentsinglesranking"], "No. 98 (21 September 2026)")

    def test_pipes_inside_links_do_not_split_a_field(self):
        _, fields = wiki.parse_infobox("{{Infobox thing\n| residence = [[Bath, Somerset|Bath]], England\n| other = x\n}}")
        self.assertEqual(fields["residence"], "Bath, England")
        self.assertEqual(fields["other"], "x")

    def test_empty_fields_are_left_out(self):
        _, fields = wiki.parse_infobox("{{Infobox thing\n| a = \n| b = value\n}}")
        self.assertEqual(fields, {"b": "value"})

    def test_no_info_box_is_not_an_error(self):
        self.assertEqual(wiki.parse_infobox("Just some text."), ("", {}))
        self.assertEqual(wiki.parse_infobox(""), ("", {}))
        self.assertEqual(wiki.parse_infobox(None), ("", {}))

    def test_an_unclosed_info_box_is_still_read(self):
        kind, fields = wiki.parse_infobox("{{Infobox tennis biography\n| plays = Left-handed")
        self.assertEqual(kind, "tennis biography")
        self.assertEqual(fields["plays"], "Left-handed")


class FactTests(NoInternetTestCase):
    def test_facts_are_curated_labelled_and_linked(self):
        _, fields = wiki.parse_infobox(fixtures.QUEENS_WIKITEXT)
        facts = wiki.curate_facts(fields, "https://en.wikipedia.org/wiki/X")
        by_label = {f["label"]: f for f in facts}
        self.assertEqual(by_label["City"]["value"], "London")
        self.assertEqual(by_label["Surface"]["value"], "Grass / outdoors")
        self.assertEqual(by_label["ATP prize money"]["value"], "€2,583,330 (2026)")
        for fact in facts:
            self.assertEqual(fact["source_url"], "https://en.wikipedia.org/wiki/X")

    def test_pictures_and_housekeeping_fields_are_not_shown(self):
        _, fields = wiki.parse_infobox(fixtures.QUEENS_WIKITEXT)
        labels = [f["label"] for f in wiki.curate_facts(fields, "u")]
        self.assertFalse(any(word in " ".join(labels).lower() for word in ("logo", "image", "caption")))

    def test_facts_follow_a_sensible_order(self):
        _, fields = wiki.parse_infobox(fixtures.QUEENS_WIKITEXT)
        labels = [f["label"] for f in wiki.curate_facts(fields, "u")]
        self.assertLess(labels.index("City"), labels.index("Surface"))
        self.assertLess(labels.index("Surface"), labels.index("ATP prize money"))

    def test_long_values_are_shortened(self):
        facts = wiki.curate_facts({"venue": "x" * 500}, "u")
        self.assertLessEqual(len(facts[0]["value"]), wiki.MAX_FACT_LENGTH)
        self.assertTrue(facts[0]["value"].endswith("…"))

    def test_an_unfamiliar_info_box_shows_its_first_plain_fields(self):
        facts = wiki.curate_facts({"image": "pic.png", "mascot": "Bear", "colour": "Blue"}, "u")
        self.assertEqual([f["label"] for f in facts], ["Mascot", "Colour"])

    def test_facts_are_read_through_the_page_text_request(self):
        kind, facts = wiki.facts("Queen's Club Championships", fixtures.make_fetch())
        self.assertEqual(kind, "tennis tournament")
        self.assertIn("Surface", [f["label"] for f in facts])

    def test_a_page_without_an_info_box_gives_no_facts(self):
        self.assertEqual(wiki.facts("Tiny Club", fixtures.make_fetch()), ("", []))

    def test_a_missing_page_gives_no_facts(self):
        self.assertEqual(wiki.facts("No Such Page", fixtures.make_fetch()), ("", []))


class SuggestionTests(NoInternetTestCase):
    def suggest(self, kind="", description="", **category_facts):
        facts = [{"label": label, "value": value} for label, value in category_facts.items()]
        return wiki.suggest_property_type(kind, description, facts)

    def test_players(self):
        self.assertEqual(self.suggest("tennis biography", ""), "player")
        self.assertEqual(self.suggest("", "British tennis player (born 2002)"), "player")

    def test_big_tournaments_are_premium(self):
        self.assertEqual(self.suggest("tennis tournament", "London tennis tournament", **{"ATP category": "ATP World Tour 500 series"}), "premium_tournament")
        self.assertEqual(self.suggest("tennis tournament", "", **{"Category": "Grand Slam"}), "premium_tournament")

    def test_challengers(self):
        self.assertEqual(self.suggest("tennis tournament", "", **{"Category": "ATP Challenger 125"}), "challenger_tournament")

    def test_junior_and_university_events(self):
        self.assertEqual(self.suggest("tennis tournament", "ITF junior tournament"), "junior_event")
        self.assertEqual(self.suggest("tennis tournament", "University tennis tournament"), "university_team")

    def test_unclear_cases_give_no_suggestion(self):
        self.assertIsNone(self.suggest("", "A small tennis club"))
        self.assertIsNone(self.suggest("tennis tournament", "tournament"))  # no category to go on
        self.assertIsNone(self.suggest("", ""))


class WholePageTests(NoInternetTestCase):
    def lookup(self, title, calls=None):
        return wiki.lookup_page(title, fixtures.make_fetch(calls=calls), today=date(2026, 10, 3))

    def test_a_tournament_page_has_everything(self):
        page = self.lookup("Queen's Club Championships")
        self.assertEqual(page["title"], "Queen's Club Championships")
        self.assertEqual(page["suggested_type"], "premium_tournament")
        self.assertEqual(page["infobox_kind"], "tennis tournament")
        self.assertTrue(page["facts"])
        self.assertEqual(len(page["pageviews"]["months"]), 12)
        self.assertEqual(page["notes"], [])

    def test_a_player_page(self):
        page = self.lookup("Toby Samuel")
        self.assertEqual(page["suggested_type"], "player")
        self.assertEqual(page["pageviews"]["annual_estimate"], 12_000)

    def test_every_fetched_item_has_a_source_link(self):
        page = self.lookup("Queen's Club Championships")
        self.assertTrue(page["url"].startswith("https://en.wikipedia.org/wiki/"))
        self.assertTrue(page["pageviews"]["source_url"].startswith("https://"))
        self.assertTrue(all(f["source_url"].startswith("https://en.wikipedia.org/wiki/") for f in page["facts"]))

    def test_a_disambiguation_page_stops_early_with_a_clear_note(self):
        calls = []
        page = self.lookup("Mercury", calls)
        self.assertEqual(page["type"], "disambiguation")
        self.assertIn("disambiguation page", page["notes"][0])
        self.assertEqual(page["facts"], [])
        self.assertIsNone(page["pageviews"])
        self.assertEqual(len(calls), 1)  # only the summary was fetched

    def test_a_page_without_extras_still_works_and_says_what_is_missing(self):
        page = self.lookup("Tiny Club")
        self.assertEqual(page["facts"], [])
        self.assertIsNone(page["pageviews"])
        notes = " ".join(page["notes"])
        self.assertIn("no info box", notes)
        self.assertIn("no page-view data", notes)

    def test_a_failure_in_the_extras_does_not_lose_the_summary(self):
        real = fixtures.make_fetch()

        def flaky(url):
            if "action=query" in url:
                raise wiki.WikipediaError("The facts service is down.")
            return real(url)

        page = wiki.lookup_page("Toby Samuel", flaky, today=date(2026, 10, 3))
        self.assertEqual(page["title"], "Toby Samuel")
        self.assertEqual(page["pageviews"]["annual_estimate"], 12_000)
        self.assertEqual(page["facts"], [])
        self.assertIn("Facts could not be read: The facts service is down.", page["notes"])

    def test_a_failure_of_the_summary_is_an_error(self):
        with self.assertRaises(wiki.NotFound):
            self.lookup("No Such Page")

    def test_it_makes_exactly_three_requests(self):
        calls = []
        self.lookup("Toby Samuel", calls)
        self.assertEqual(len(calls), 3)  # summary, info box text, page views


class DownloaderTests(unittest.TestCase):
    """fetch_json itself, with the operating system's downloader replaced by stand-ins."""

    def run_with(self, outcome):
        with mock.patch("urllib.request.urlopen", **outcome):
            return wiki.fetch_json("https://en.wikipedia.org/x")

    def test_a_good_reply_is_decoded(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value.read.return_value = json.dumps({"ok": 1}).encode()
        self.assertEqual(self.run_with({"return_value": reply}), {"ok": 1})

    def http_error(self, code):
        error = urllib.error.HTTPError("u", code, "error", {}, io.BytesIO())
        self.addCleanup(error.close)  # tidy up, so the test run prints no warnings
        return error

    def test_a_404_means_not_found(self):
        with self.assertRaises(wiki.NotFound):
            self.run_with({"side_effect": self.http_error(404)})

    def test_other_http_errors_are_explained(self):
        error = self.http_error(500)
        with self.assertRaises(wiki.WikipediaError) as caught:
            self.run_with({"side_effect": error})
        self.assertIn("500", str(caught.exception))
        self.assertNotIsInstance(caught.exception, wiki.NotFound)

    def test_no_connection_is_explained_in_plain_english(self):
        for failure in (urllib.error.URLError("no route"), TimeoutError(), ConnectionResetError()):
            with self.assertRaises(wiki.WikipediaError) as caught:
                self.run_with({"side_effect": failure})
            self.assertIn("Could not reach Wikipedia", str(caught.exception))

    def test_a_certificate_problem_has_its_own_helpful_message(self):
        failure = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        with self.assertRaises(wiki.WikipediaError) as caught:
            self.run_with({"side_effect": failure})
        self.assertIn("Install Certificates.command", str(caught.exception))

    def test_an_unreadable_reply_is_explained(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value.read.return_value = b"<html>not json</html>"
        with self.assertRaises(wiki.WikipediaError) as caught:
            self.run_with({"return_value": reply})
        self.assertIn("could not be read", str(caught.exception))

    def test_the_request_says_who_is_asking(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value.read.return_value = b"{}"
        with mock.patch("urllib.request.urlopen", return_value=reply) as opener:
            wiki.fetch_json("https://en.wikipedia.org/x")
        request = opener.call_args[0][0]
        self.assertIn("SponsorshipScout", request.get_header("User-agent"))

    def test_it_uses_a_trusted_certificate_list_and_a_time_limit(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value.read.return_value = b"{}"
        with mock.patch("urllib.request.urlopen", return_value=reply) as opener:
            wiki.fetch_json("https://en.wikipedia.org/x")
        self.assertEqual(opener.call_args.kwargs["timeout"], wiki.TIMEOUT_SECONDS)
        self.assertIsInstance(opener.call_args.kwargs["context"], ssl.SSLContext)


if __name__ == "__main__":
    unittest.main()
