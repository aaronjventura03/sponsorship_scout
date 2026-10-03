"""Stand-in Wikipedia responses for the tests, so no test ever touches the internet.

The shapes copy the real Wikipedia / Wikimedia replies (checked against the live services
on 3 October 2026). make_fetch() builds a replacement for wikipedia_lookup.fetch_json that
answers from a small catalogue of pages.
"""

import urllib.parse

import wikipedia_lookup as wiki

# ---------------------------------------------------------------------------
# Real-shaped info boxes (trimmed from the live pages)
# ---------------------------------------------------------------------------
QUEENS_WIKITEXT = """{{Infobox tennis tournament
| name            = Queen's Club Championships
| logo            = HSBC Championships logo 2.jpg
| current         =
|type = joint
| event name      = HSBC Championships
| founded         = {{start date and age|df=yes|1886}}
| editions        = 122 (2025)
| city            = London
| country         = United Kingdom
| venue           = [[The Queen's Club]]
| ATP category        = [[Grand Prix tennis circuit]]<br />(1970–1989)<br />[[ATP World Tour 500 series]]<br />(2015–)
|WTA tier = ILTF Europe Circuit<br>(1913–1970)<br />[[WTA 500]]<br />(2025–)
| surface         = [[Grass court|Grass]] / outdoors
| WTA draw        = 28S / 24Q / 16D
| ATP draw        =  32S / 32Q / 24D
| WTA prize money = $1,915,000 (2026)
| ATP prize money = €2,583,330 (2026)
| website         = {{URL|https://www.queensclub.co.uk/|queensclub.co.uk}}
| men's singles   = {{flagicon|ARG}} [[Francisco Cerundolo]]
}}

The '''Queen's Club Championships''' is an annual professional [[tennis]] tournament."""

TOBY_WIKITEXT = """{{Infobox tennis biography
|name                              = Toby Samuel
|country_represented               = {{flagicon|GBR}} Great Britain
|image                             = Samuel WMQ23 (53061881914).jpg
|caption                           = Samuel at the [[2023 Wimbledon Championships]]
|residence                         = [[Bath, Somerset|Bath]], England, UK
|birth_date                        = {{birth date and age|2002|9|6|df=y}}
|height                            = {{convert|1.91|m|abbr=on}}
|plays                             = Right-handed (two-handed backhand)
|careerprizemoney                  = US $648,325<ref name="atp">{{cite web|url=https://example.com}}</ref>
|singlesrecord                     = 3–5
|highestsinglesranking             = No. 95 (14 September 2026)
|currentsinglesranking             = No. 98 (21 September 2026)
}}

'''Toby Samuel''' (born 6 September 2002) is a British professional tennis player."""

# 12 complete months of page views (October 2025 to September 2026).
MONTHS = [f"2025{m:02d}" for m in (10, 11, 12)] + [f"2026{m:02d}" for m in range(1, 10)]


def pageview_items(article, views):
    return [
        {"project": "en.wikipedia", "article": article, "granularity": "monthly", "timestamp": f"{month}0100",
         "access": "all-access", "agent": "user", "views": count}
        for month, count in zip(MONTHS, views)
    ]


# ---------------------------------------------------------------------------
# A small catalogue of pages
# ---------------------------------------------------------------------------
CATALOGUE = {
    "Queen's Club Championships": {
        "type": "standard",
        "description": "London tennis tournament",
        "extract": "The Queen's Club Championships is an annual professional tennis tournament, held on grass courts.",
        "wikitext": QUEENS_WIKITEXT,
        "views": [2143, 2500, 1800, 2000, 2200, 2600, 3100, 9000, 52000, 41000, 3000, 2598],  # total 123,941
    },
    "Toby Samuel": {
        "type": "standard",
        "description": "British tennis player (born 2002)",
        "extract": "Toby Samuel is a British professional tennis player.",
        "wikitext": TOBY_WIKITEXT,
        "views": [1000] * 12,  # average 1,000, so a year is 12,000
    },
    "Ilkley Trophy": {  # the Wikipedia page of the Lexus Ilkley Open (a saved property)
        "type": "standard",
        "description": "Tennis tournament on grass courts",
        "extract": "The Lexus Ilkley Open is a professional tennis tournament played on grass courts.",
        "wikitext": "",
        "views": [400] * 12,  # average 400, so a year is 4,800
    },
    "Mercury": {
        "type": "disambiguation",
        "description": "Topics referred to by the same term",
        "extract": "Mercury most commonly refers to the planet.",
        "wikitext": "",
        "views": None,
    },
    "Tiny Club": {  # a page with no info box and no page-view data
        "type": "standard",
        "description": "A small tennis club",
        "extract": "Tiny Club is a small tennis club.",
        "wikitext": "'''Tiny Club''' is a small tennis club with no info box.",
        "views": None,
    },
}

# What searching for a name returns (lower-case query -> page titles).
SEARCHES = {
    "queen's club championships": ["Queen's Club Championships"],
    "toby samuel": ["Toby Samuel"],
    "mercury": ["Mercury"],
    "tiny club": ["Tiny Club"],
    "tennis": ["Queen's Club Championships", "Toby Samuel"],
}


def _title_from_url(url, marker):
    """Pull the page title out of a web address: the part after `marker`, decoded."""
    tail = url.split(marker, 1)[1].split("?", 1)[0].split("/", 1)[0]
    return urllib.parse.unquote(tail).replace("_", " ")


def make_fetch(catalogue=None, searches=None, calls=None):
    """A stand-in for wikipedia_lookup.fetch_json that answers from the catalogue.
    If `calls` is a list, every web address requested is appended to it."""
    catalogue = CATALOGUE if catalogue is None else catalogue
    searches = SEARCHES if searches is None else searches

    def fetch(url):
        if calls is not None:
            calls.append(url)
        if "/rest.php/v1/search/page" in url:
            query = urllib.parse.unquote(url.split("q=", 1)[1].split("&", 1)[0]).lower()
            return {"pages": [
                {"id": index, "key": title.replace(" ", "_"), "title": title,
                 "description": catalogue[title]["description"],
                 "excerpt": f'The <span class="searchmatch">{title.split()[0]}</span> page &amp; more'}
                for index, title in enumerate(searches.get(query, []))
            ]}
        if "/api/rest_v1/page/summary/" in url:
            title = _title_from_url(url, "/page/summary/")
            if title not in catalogue:
                raise wiki.NotFound("no such page")
            page = catalogue[title]
            return {"type": page["type"], "title": title, "description": page["description"], "extract": page["extract"],
                    "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}}}
        if "action=query" in url:
            title = urllib.parse.unquote(url.split("titles=", 1)[1].split("&", 1)[0]).replace("_", " ")
            page = catalogue.get(title)
            if page is None:
                return {"query": {"pages": [{"title": title, "missing": True}]}}
            return {"query": {"pages": [{"pageid": 1, "title": title,
                                         "revisions": [{"slots": {"main": {"content": page["wikitext"]}}}]}]}}
        if "/metrics/pageviews/per-article/" in url:
            title = _title_from_url(url, "/user/")
            page = catalogue.get(title)
            if page is None or page["views"] is None:
                raise wiki.NotFound("no page views")
            return {"items": pageview_items(title.replace(" ", "_"), page["views"])}
        raise AssertionError(f"The test stand-in was asked for an address it does not know: {url}")

    return fetch
