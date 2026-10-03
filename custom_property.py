"""Turns a Wikipedia lookup plus the user's own entries into a property record.

The record has exactly the same fields as a row of data/properties.csv, so the existing
scoring, brand matching and pitch code can use it without any changes.

Honesty rules built in:
  - Every figure is marked "sourced" or "estimated" by the user.
  - A figure marked "sourced" must say where it came from, or it is rejected.
  - A figure left blank is simply "not measured": the scoring shares its weight across
    the figures that are present, exactly as it does for Roehampton's engagement.
  - Nothing is guessed on the user's behalf except the starting age profile, which is
    clearly labelled as a default that has not been researched.
"""

from datetime import date

from matching import AGE_BANDS

# ---------------------------------------------------------------------------
# The five figures the score uses. The key is the factor name used by scoring.py.
#   column  - the properties.csv column holding the number
#   prefix  - the start of its _source / _source_url / _confidence columns
#   whole   - True if it must be a whole number
# ---------------------------------------------------------------------------
FIGURES = {
    "audience": {"column": "annual_audience_reach", "prefix": "audience", "label": "Audience reach (people)",
                 "whole": True, "low": 0, "high": None},
    "engagement": {"column": "engagement_per_post", "prefix": "engagement",
                   "label": "Engagements per post (median likes + comments)", "whole": True, "low": 0, "high": None},
    "demographics": {"column": "high_income_share_pct", "prefix": "high_income",
                     "label": "Audience in higher-income brackets (%)", "whole": False, "low": 0, "high": 100},
    "media": {"column": "broadcast_tier", "prefix": "broadcast", "label": "Broadcast tier (0 to 10)",
              "whole": True, "low": 0, "high": 10},
    "prestige": {"column": "prestige_rating", "prefix": "prestige", "label": "Prestige (1 to 10)",
                 "whole": True, "low": 1, "high": 10},
}

SOURCED, ESTIMATED = "sourced", "estimated"

# Used to label the audience figure when it comes from Wikipedia page views.
PAGEVIEW_SOURCE = (
    "Wikipedia page views: average of the last {months} complete months x 12 "
    "(a proxy for public interest, not attendance)"
)

# A starting audience age profile for each property type, until the real one is researched.
# These are the same judgement-based profiles as the five properties in properties.csv.
DEFAULT_AGE_PROFILES = {
    "premium_tournament": (8, 12, 20, 35, 25),
    "challenger_tournament": (10, 15, 20, 30, 25),
    "player": (10, 25, 28, 25, 12),
    "university_team": (1, 85, 8, 4, 2),
    "junior_event": (45, 4, 4, 42, 5),
}
GENERIC_AGE_PROFILE = (10, 20, 25, 30, 15)
DEFAULT_AGE_SOURCE = "Default profile for this property type; not researched"
ENTERED_AGE_SOURCE = "Entered by you"


def age_profile_for(property_type):
    """The default age profile for a property type, as {band part: percent}."""
    numbers = DEFAULT_AGE_PROFILES.get(property_type, GENERIC_AGE_PROFILE)
    return {part: number for (part, _label), number in zip(AGE_BANDS, numbers)}


def _first_words(text, limit=160):
    """A short description: the text cut at a word boundary, ending cleanly."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


def default_values(page, property_types, use_pageviews=True, chosen_type=None):
    """The form's starting values, built from a Wikipedia page (see wikipedia_lookup.lookup_page).

    Only what Wikipedia actually gave us is filled in: the name, a suggested property type
    (or the type the user has already chosen) and, if ticked, the page views as the audience
    figure. Everything else starts blank.
    """
    suggested = page.get("suggested_type")
    property_type = chosen_type or (suggested if suggested in property_types else None)
    description = (page.get("description") or "").strip()
    description = description[:1].upper() + description[1:] if description else _first_words(page.get("extract"))

    figures = {
        factor: {"value": None, "mode": ESTIMATED, "source": "", "url": ""} for factor in FIGURES
    }
    views = page.get("pageviews")
    if use_pageviews and views:
        figures["audience"] = {
            "value": views["annual_estimate"],
            "mode": SOURCED,
            "source": PAGEVIEW_SOURCE.format(months=len(views["months"])),
            "url": views["source_url"],
        }
    return {
        "name": page.get("title", ""),
        "description": description or "Tennis property",
        "property_type": property_type,
        "audience_includes_minors": property_type == "junior_event",
        "figures": figures,
        "engagement_rate_pct": None,
        "engagement_account": "",
        "engagement_followers": None,
        "age_profile": age_profile_for(property_type),
        "age_mode": ESTIMATED,
        "age_source": DEFAULT_AGE_SOURCE,
        "wikipedia_title": page.get("title", ""),
        "wikipedia_url": page.get("url", ""),
    }


def _confidence(value, mode, source):
    """The confidence label stored in the data: published, calculated or estimate."""
    if value is None:
        return ""
    if mode == ESTIMATED:
        return "estimate"
    return "calculated" if source.startswith("Wikipedia page views") else "published"


def _slug(text):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def build_property(values, today=None):
    """Check the form's values and build a property record from them.

    Returns (property, errors). If there are any errors the property is None and every
    error is a plain-English sentence to show the user.
    """
    errors = []
    name = (values.get("name") or "").strip()
    if not name:
        errors.append("Give the property a name.")
    if not values.get("property_type"):
        errors.append("Choose a property type.")

    # --- the five figures ---
    for factor, spec in FIGURES.items():
        entry = values["figures"][factor]
        value = entry.get("value")
        if value is None:
            continue
        if value < spec["low"] or (spec["high"] is not None and value > spec["high"]):
            top = f" and {spec['high']}" if spec["high"] is not None else " or more"
            errors.append(f"{spec['label']}: enter a number between {spec['low']}{top}.")
        if entry.get("mode") == SOURCED and not (entry.get("source") or "").strip():
            errors.append(f"{spec['label']}: add a source, or mark it as Estimated.")
    rate = values.get("engagement_rate_pct")
    if rate is not None and not 0 <= rate <= 100:
        errors.append("Engagement rate: enter a percentage between 0 and 100.")

    # --- the audience age profile (needed for brand matching) ---
    profile = values.get("age_profile") or {}
    numbers = [profile.get(part) for part, _label in AGE_BANDS]
    if any(number is None for number in numbers):
        errors.append("Fill in all five audience age groups.")
    elif sum(numbers) != 100:
        errors.append(f"The audience age groups must total 100 (they total {sum(numbers)}).")
    if values.get("age_mode") == SOURCED and not (values.get("age_source") or "").strip():
        errors.append("Audience age profile: add a source, or mark it as Estimated.")

    if errors:
        return None, errors

    today = today or date.today()
    default_profile = age_profile_for(values["property_type"])
    # The label must say what really happened: the stock default text only stays if the profile is
    # still the default. If the user changed the numbers, it says so instead.
    typed_source = (values.get("age_source") or "").strip()
    if typed_source == DEFAULT_AGE_SOURCE:
        typed_source = ""
    age_source = typed_source or (DEFAULT_AGE_SOURCE if profile == default_profile else ENTERED_AGE_SOURCE)

    prop = {
        "id": f"LOOKUP-{_slug(values.get('wikipedia_title') or name)}",
        "name": name,
        "property_type": values["property_type"],
        "market": "",
        "description": (values.get("description") or "").strip() or "Tennis property",
        "date_collected": today.isoformat(),
        "engagement_rate_pct": "" if rate is None else rate,
        "engagement_account": (values.get("engagement_account") or "").strip(),
        "engagement_followers": "" if values.get("engagement_followers") is None else values["engagement_followers"],
        "age_profile_source": age_source,
        "age_profile_confidence": "estimate" if values.get("age_mode") != SOURCED else "published",
        "audience_includes_minors": bool(values.get("audience_includes_minors")),
        "is_placeholder": False,
        "from_wikipedia": True,
        "wikipedia_title": values.get("wikipedia_title", ""),
        "wikipedia_url": values.get("wikipedia_url", ""),
    }
    for part, _label in AGE_BANDS:
        prop[f"age_{part}_pct"] = profile[part]

    for factor, spec in FIGURES.items():
        entry = values["figures"][factor]
        value = entry.get("value")
        source = (entry.get("source") or "").strip()
        prefix = spec["prefix"]
        # Whole numbers are stored as whole numbers, and so are whole percentages (40.0 becomes 40).
        prop[spec["column"]] = "" if value is None else (int(value) if spec["whole"] or float(value).is_integer() else value)
        prop[f"{prefix}_source"] = source if value is not None else ""
        prop[f"{prefix}_source_url"] = (entry.get("url") or "").strip() if value is not None else ""
        confidence = _confidence(value, entry.get("mode"), source)
        if value is None and factor == "engagement":
            confidence = "not measurable"
        prop[f"{prefix}_confidence"] = confidence
    if prop["engagement_per_post"] == "":
        prop["engagement_source"] = "Not measurable: no figure was entered; the weight is redistributed across the other factors"
    return prop, []
