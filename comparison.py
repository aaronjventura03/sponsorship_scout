"""Like-for-like comparison: score every property's audience on the SAME measure.

The problem: a property's normal audience figure is whatever could be found for it
(attendance plus a TV audience for Queen's, Instagram followers for a player, a rough
guess for a small event). A property looked up on Wikipedia only has page views. Those
are different things, so ranking them side by side is not fair.

The fix: in "like for like" mode every property's audience is its Wikipedia page views
over the same last 12 complete months, fetched together. This module does two jobs:

  1. ensure_page_views()  fetches page views for the properties that have a Wikipedia page
  2. like_for_like()      returns COPIES of the properties with the audience swapped for
                          page views, ready to go through the normal scoring unchanged

Rules:
  - The saved data is never changed. Normal mode still uses the real audience figures.
  - A property with no Wikipedia page (or no page-view data) gets a BLANK audience, so the
    scoring treats it as "not measured" and shares its weight across its other factors.
  - If Wikipedia cannot be reached, the problem is reported and the caller falls back to
    the normal scores. A failed download is never mistaken for "this property has no page".
"""

import wikipedia_lookup as wiki
from custom_property import PAGEVIEW_SOURCE

NO_PAGE_SOURCE = (
    "No Wikipedia page views available for this property, so its audience is not measured on the same basis"
)


def ensure_page_views(cache, titles, fetch=None, today=None):
    """Fetch page views for any title not already in `cache` (a dictionary the caller keeps).

    `cache` maps a page title to its page views, or to None if Wikipedia has no page-view data
    for it. A title that could not be fetched because of a network problem is NOT stored,
    so it is tried again next time. Blank titles are skipped and repeats are fetched once.
    Returns a list of plain-English problems (empty if everything worked).
    """
    problems = []
    for title in dict.fromkeys(t for t in titles if t):
        if title in cache:
            continue
        try:
            cache[title] = wiki.page_views(title, fetch, today)  # None means "no data for this page"
        except wiki.WikipediaError as problem:
            problems.append(f"{title}: {problem}")
    return problems


def like_for_like(properties, views_by_title):
    """Copies of `properties` whose audience is their Wikipedia page views (a year's worth,
    from the last 12 complete months), so every property is measured the same way.

    Each copy keeps the original figure in "original_audience_reach" and "original_audience_source",
    and is marked with "like_for_like": True. The input properties are not changed.
    """
    converted = []
    for prop in properties:
        copy = dict(prop)
        copy["original_audience_reach"] = prop.get("annual_audience_reach", "")
        copy["original_audience_source"] = prop.get("audience_source", "")
        copy["like_for_like"] = True

        views = views_by_title.get(prop.get("wikipedia_title") or "")
        if views:
            copy["annual_audience_reach"] = views["annual_estimate"]
            copy["audience_source"] = PAGEVIEW_SOURCE.format(months=len(views["months"]))
            copy["audience_source_url"] = views["source_url"]
            copy["audience_confidence"] = "calculated"
        else:
            copy["annual_audience_reach"] = ""  # blank = "not measured": its weight is shared across the other factors
            copy["audience_source"] = NO_PAGE_SOURCE
            copy["audience_source_url"] = ""
            copy["audience_confidence"] = ""
        converted.append(copy)
    return converted
