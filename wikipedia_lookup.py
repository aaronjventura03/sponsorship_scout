"""Looks up a tournament or player on Wikipedia using its free public APIs.

No API key, no account and no payment is needed. Three public services are used:

  1. Wikipedia search       finds pages that match a name you type
  2. Wikipedia page summary the short description and opening paragraph
  3. Wikimedia page views   how many people viewed the page each month
     (plus the page's "info box" is read for facts such as surface, category or ranking)

Every fetched item carries a link to where it came from.

How the code is organised, in plain English:
  - fetch_json() is the only function that touches the internet.
  - Every other function takes an optional `fetch` argument (fetch_json is used if it is
    left out). The tests pass in a stand-in instead, so they never need the internet.
  - If Wikipedia cannot be reached or has no such page, a WikipediaError is raised with
    a plain-English message that the app shows to the user.

Wikipedia's text is available under the CC BY-SA 4.0 licence.
"""

import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

# Wikimedia asks every program that uses its APIs to say who it is.
USER_AGENT = "SponsorshipScout/1.0 (educational portfolio project)"
TIMEOUT_SECONDS = 10

SEARCH_LIMIT = 5          # how many matching pages to offer
PAGEVIEW_MONTHS = 12      # how many full months of page views to look at
MAX_FACT_LENGTH = 140     # long fact values are shortened to this many characters

LICENCE_NAME = "CC BY-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"

_PAGE_URL = "https://en.wikipedia.org/wiki/{title}"
_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page?q={query}&limit={limit}"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKITEXT_URL = (
    "https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content"
    "&rvslots=main&rvsection=0&titles={title}&format=json&formatversion=2"
)
_PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
    "all-access/user/{title}/monthly/{start}/{end}"
)
# A human-friendly page where anyone can see the same page-view numbers.
_PAGEVIEWS_TOOL_URL = (
    "https://pageviews.wmcloud.org/?project=en.wikipedia.org&platforms=all-access"
    "&agent=user&redirects=0&range=latest-20&pages={title}"
)


class WikipediaError(Exception):
    """Something went wrong talking to Wikipedia. The message is safe to show to the user."""


class NotFound(WikipediaError):
    """Wikipedia has no such page (or no data for it)."""


# ---------------------------------------------------------------------------
# The only function that uses the internet
# ---------------------------------------------------------------------------
def _secure_context():
    """The list of trusted certificates used to check that we are really talking to
    Wikipedia. Python installed from python.org on a Mac often has no such list, so we
    use the one that comes with the `certifi` package (installed together with Streamlit)
    when it is available."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_json(url):
    """Download a web address and return its JSON reply as Python data."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=_secure_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as problem:
        if problem.code == 404:
            raise NotFound("Wikipedia has no data for that page.") from problem
        raise WikipediaError(f"Wikipedia returned an error (code {problem.code}). Please try again later.") from problem
    except urllib.error.URLError as problem:
        if isinstance(problem.reason, ssl.SSLCertVerificationError):
            raise WikipediaError(
                "This computer could not verify Wikipedia's secure connection (a certificate problem). "
                "If you installed Python from python.org, open the Python folder in Applications and run "
                "'Install Certificates.command', then try again."
            ) from problem
        raise WikipediaError("Could not reach Wikipedia. Check your internet connection and try again.") from problem
    except (TimeoutError, OSError) as problem:
        raise WikipediaError("Could not reach Wikipedia. Check your internet connection and try again.") from problem
    except json.JSONDecodeError as problem:
        raise WikipediaError("Wikipedia sent a reply that could not be read. Please try again.") from problem


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _get(url, fetch):
    """Download `url` with the given fetch function, or the real fetch_json if none is given.
    (The real function is looked up when called, so tests can replace it.)"""
    return (fetch or fetch_json)(url)


def encode_title(title):
    """A page title as it appears in a web address: spaces become underscores and
    special characters (such as the apostrophe in Queen's) are percent-encoded."""
    return urllib.parse.quote(title.strip().replace(" ", "_"), safe="")


def page_url(title):
    """The normal web page for a Wikipedia article, for use as a source link."""
    return _PAGE_URL.format(title=urllib.parse.quote(title.strip().replace(" ", "_"), safe="_',()!*~:-"))


def _strip_html(text):
    """Remove HTML tags (search results highlight matches with <span> tags)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


# ---------------------------------------------------------------------------
# 1. Search
# ---------------------------------------------------------------------------
def search(query, fetch=None, limit=SEARCH_LIMIT):
    """Find Wikipedia pages matching a name. Returns a list of dictionaries with
    "title", "description", "excerpt" and "url", best match first (possibly empty)."""
    query = (query or "").strip()
    if not query:
        raise WikipediaError("Type a tournament or player name to search for.")
    data = _get(_SEARCH_URL.format(query=urllib.parse.quote(query, safe=""), limit=limit), fetch)
    return [
        {
            "title": page["title"],
            "description": page.get("description") or "",
            "excerpt": _strip_html(page.get("excerpt")),
            "url": page_url(page.get("key") or page["title"]),
        }
        for page in data.get("pages", [])
    ]


# ---------------------------------------------------------------------------
# 2. Page summary
# ---------------------------------------------------------------------------
def summary(title, fetch=None):
    """The short description and opening paragraph of a page."""
    data = _get(_SUMMARY_URL.format(title=encode_title(title)), fetch)
    url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page") or page_url(data.get("title") or title)
    return {
        "title": data.get("title") or title,
        "type": data.get("type") or "standard",  # "disambiguation" means "choose a more specific page"
        "description": data.get("description") or "",
        "extract": data.get("extract") or "",
        "url": url,
    }


# ---------------------------------------------------------------------------
# 3. Monthly page views
# ---------------------------------------------------------------------------
def _month_window(today, months):
    """The last `months` COMPLETE months before `today`, as (start, end) dates."""
    end = today.replace(day=1) - timedelta(days=1)       # the last day of last month
    year, month = end.year, end.month - (months - 1)
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1), end


def page_views(title, fetch=None, today=None, months=PAGEVIEW_MONTHS):
    """Monthly page views over the last `months` complete months, as a measure of
    public interest. Returns None if Wikipedia has no page-view data for the page.

    Returns a dictionary with:
      "months"           - [{"month": "2026-01", "views": 1234}, ...] oldest first
      "average_monthly"  - the average views per month
      "annual_estimate"  - the average x 12 (a full year's worth of views)
      "source_url"       - a human-friendly page showing the same numbers
      "api_url"          - the Wikimedia API address the numbers came from
    """
    start, end = _month_window(today or date.today(), months)
    api_url = _PAGEVIEWS_URL.format(title=encode_title(title), start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    try:
        data = _get(api_url, fetch)
    except NotFound:
        return None
    items = data.get("items") or []
    if not items:
        return None
    rows = sorted(
        ({"month": f"{item['timestamp'][:4]}-{item['timestamp'][4:6]}", "views": int(item["views"])} for item in items),
        key=lambda row: row["month"],
    )
    average = sum(row["views"] for row in rows) / len(rows)
    return {
        "months": rows,
        "average_monthly": round(average),
        "annual_estimate": round(average * 12),
        "source_url": _PAGEVIEWS_TOOL_URL.format(title=encode_title(title)),
        "api_url": api_url,
    }


# ---------------------------------------------------------------------------
# 4. Facts from the page's info box
# ---------------------------------------------------------------------------
# The info box is the panel at the top right of a Wikipedia page. We read the page's
# raw text (called "wikitext") and pick the facts a sponsor would care about.
# (key as it is written in the info box with spaces and capitals removed, label to show)
FACT_FIELDS = [
    ("city", "City"), ("location", "Location"), ("country", "Country"),
    ("countryrepresented", "Represents"), ("venue", "Venue"), ("surface", "Surface"),
    ("founded", "Founded"), ("editions", "Editions"),
    ("atpcategory", "ATP category"), ("wtatier", "WTA tier"), ("category", "Category"),
    ("atpdraw", "ATP draw"), ("wtadraw", "WTA draw"), ("draw", "Draw"),
    ("atpprizemoney", "ATP prize money"), ("wtaprizemoney", "WTA prize money"), ("prizemoney", "Prize money"),
    ("birthdate", "Born"), ("birthplace", "Birthplace"), ("residence", "Residence"),
    ("height", "Height"), ("plays", "Plays"),
    ("currentsinglesranking", "Current singles ranking"), ("highestsinglesranking", "Highest singles ranking"),
    ("singlesrecord", "Singles record (career)"), ("singlestitles", "Singles titles"),
    ("careerprizemoney", "Career prize money"), ("coach", "Coach"), ("website", "Website"),
]
# Info box fields that are pictures or housekeeping, never shown as facts.
_IGNORED_FIELDS = {"name", "logo", "image", "caption", "alt", "imagesize", "imageupright", "fullname", "type", "current"}


def _find_infobox(wikitext):
    """The text of the first {{Infobox ...}} in the page, or None."""
    match = re.search(r"\{\{\s*Infobox", wikitext, re.IGNORECASE)
    if not match:
        return None
    depth, position = 0, match.start()
    while position < len(wikitext):
        if wikitext.startswith("{{", position):
            depth += 1
            position += 2
        elif wikitext.startswith("}}", position):
            depth -= 1
            position += 2
            if depth == 0:
                return wikitext[match.start():position]
        else:
            position += 1
    return wikitext[match.start():]  # the box was never closed; use what there is


def _split_top_level(text, separator="|"):
    """Split on a separator, ignoring separators inside {{ }} or [[ ]]."""
    parts, depth, current, position = [], 0, [], 0
    while position < len(text):
        pair = text[position:position + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            position += 2
        elif pair in ("}}", "]]"):
            depth -= 1
            current.append(pair)
            position += 2
        elif text[position] == separator and depth == 0:
            parts.append("".join(current))
            current = []
            position += 1
        else:
            current.append(text[position])
            position += 1
    parts.append("".join(current))
    return parts


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


def _format_date(numbers):
    """[1886] -> '1886'; [2002, 9] -> 'September 2002'; [2002, 9, 6] -> '6 September 2002'."""
    year = numbers[0]
    if len(numbers) >= 2 and 1 <= int(numbers[1]) <= 12:
        month = _MONTHS[int(numbers[1]) - 1]
        if len(numbers) >= 3:
            return f"{int(numbers[2])} {month} {year}"
        return f"{month} {year}"
    return str(year)


def _template_text(body):
    """Turn one simple {{template|...}} (no templates inside it) into plain text."""
    parts = [part.strip() for part in body.split("|")]
    name, args = parts[0].lower(), parts[1:]
    positional = [a for a in args if "=" not in a]
    if name in ("start date", "start date and age", "birth date", "birth date and age", "death date", "end date"):
        numbers = [a for a in positional if a.isdigit()]
        return _format_date(numbers) if numbers else ""
    if name == "convert":
        return " ".join(positional[:2])
    if name == "url":
        return positional[1] if len(positional) > 1 else (positional[0] if positional else "")
    if name in ("nowrap", "small", "nobr"):
        return positional[0] if positional else ""
    if name in ("plainlist", "unbulleted list", "ubl", "flatlist", "hlist"):
        items = []
        for argument in positional:
            items += [line.strip(" *\t") for line in argument.splitlines()]
        return ", ".join(item for item in items if item)
    return ""  # anything else (flag icons, citations, formatting helpers) is dropped


def clean_wikitext(value):
    """Turn a raw info box value into plain readable text.
    Removes references, comments, links and templates, keeping the words that matter."""
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref[^>]*/>", "", value)
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.DOTALL)
    value = re.sub(r"<br\s*/?>", ", ", value, flags=re.IGNORECASE)
    # [[Page|text]] -> text, [[Page]] -> Page, and drop file/image links
    value = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", value)
    value = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", value)  # [url text] -> text
    for _ in range(10):  # replace the innermost templates first, until none are left
        replaced = re.sub(r"\{\{([^{}]*)\}\}", lambda found: _template_text(found.group(1)), value)
        if replaced == value:
            break
        value = replaced
    value = re.sub(r"'{2,}", "", value)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(,\s*){2,}", ", ", value)
    return value.strip(" ,;/")


def parse_infobox(wikitext):
    """Read the first info box in a page's wikitext.
    Returns (kind, fields): kind is e.g. "tennis tournament" (or "" if there is no
    info box) and fields maps a simplified field name to its cleaned text."""
    box = _find_infobox(wikitext or "")
    if box is None:
        return "", {}
    inner = box[2:-2] if box.endswith("}}") else box[2:]
    chunks = _split_top_level(inner)
    kind = re.sub(r"^\s*infobox\s*", "", chunks[0], flags=re.IGNORECASE).strip().lower()
    fields = {}
    for chunk in chunks[1:]:
        if "=" not in chunk:
            continue
        key, _, raw_value = chunk.partition("=")
        simple_key = re.sub(r"[\s_'\-]", "", key.strip().lower())
        cleaned = clean_wikitext(raw_value)
        if simple_key and cleaned and simple_key not in fields:
            fields[simple_key] = cleaned
    return kind, fields


def _shorten(text):
    return text if len(text) <= MAX_FACT_LENGTH else text[: MAX_FACT_LENGTH - 1].rstrip() + "…"


def curate_facts(fields, source_url):
    """Pick the useful facts from an info box. Each fact is a dictionary with
    "label", "value" and "source_url" (the page it was read from)."""
    facts = [
        {"label": label, "value": _shorten(fields[key]), "source_url": source_url}
        for key, label in FACT_FIELDS
        if key in fields
    ]
    if not facts:  # an info box we do not recognise: show its first few plain fields
        for key, value in fields.items():
            if key not in _IGNORED_FIELDS and len(facts) < 6:
                facts.append({"label": key.capitalize(), "value": _shorten(value), "source_url": source_url})
    return facts


def facts(title, fetch=None):
    """Facts from a page's info box. Returns (kind, list of facts); both empty if the
    page has no info box."""
    data = _get(_WIKITEXT_URL.format(title=encode_title(title)), fetch)
    pages = (data.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing") or not pages[0].get("revisions"):
        return "", []
    wikitext = pages[0]["revisions"][0]["slots"]["main"]["content"]
    kind, fields = parse_infobox(wikitext)
    return kind, curate_facts(fields, page_url(title))


# ---------------------------------------------------------------------------
# What kind of property is it? (a suggestion only: the user always decides)
# ---------------------------------------------------------------------------
_PREMIUM_WORDS = ["grand slam", "atp finals", "atp 1000", "atp masters", "masters 1000", "atp 500",
                  "world tour 500", "wta 1000", "wta 500", "wta premier", "wta finals"]


def suggest_property_type(kind, description, fact_list):
    """A best guess at the property type, using the info box type, the page's one-line
    description and the category facts. Returns None when it is unclear."""
    category_text = " ".join(f["value"] for f in fact_list if "category" in f["label"].lower() or "tier" in f["label"].lower())
    text = f"{kind} {description} {category_text}".lower()
    if "tennis biography" in text or "tennis player" in text:
        return "player"
    if "tournament" in text or "championships" in text or "open" in text or "tennis tournament" in kind:
        if "junior" in text or "itf j" in text:
            return "junior_event"
        if "university" in text or "college" in text or "bucs" in text:
            return "university_team"
        if any(word in text for word in _PREMIUM_WORDS):
            return "premium_tournament"
        if "challenger" in text or "itf" in text:
            return "challenger_tournament"
    return None


# ---------------------------------------------------------------------------
# Everything about one page, in one call
# ---------------------------------------------------------------------------
def lookup_page(title, fetch=None, today=None):
    """Fetch the summary, info box facts and page views for one Wikipedia page.

    The summary is required: if it fails, a WikipediaError is raised. The facts and
    page views are extras: if either fails, a plain-English note is added to "notes"
    and the rest still works.
    """
    page = summary(title, fetch)
    page["notes"] = []
    page["facts"], page["infobox_kind"], page["pageviews"] = [], "", None
    if page["type"] == "disambiguation":
        page["notes"].append(
            "This is a disambiguation page (a list of different pages with this name). "
            "Go back and choose a more specific page."
        )
        return page

    try:
        page["infobox_kind"], page["facts"] = facts(page["title"], fetch)
    except WikipediaError as problem:
        page["notes"].append(f"Facts could not be read: {problem}")
    if not page["facts"] and not page["notes"]:
        page["notes"].append("This page has no info box, so no facts were found.")

    try:
        page["pageviews"] = page_views(page["title"], fetch, today)
        if page["pageviews"] is None:
            page["notes"].append("Wikipedia has no page-view data for this page.")
    except WikipediaError as problem:
        page["notes"].append(f"Page views could not be fetched: {problem}")

    page["suggested_type"] = suggest_property_type(page["infobox_kind"], page["description"], page["facts"])
    return page
