"""Writes the one-page partnership pitch.

VERSION 1 uses a fixed template filled in with data. No AI is involved.

THE PITCH IS WRITTEN FOR THE BRAND. It talks about benefits to the brand and
contains no scores, ratings or other internal analysis. Those belong in a
separate analysis panel in the app, not in what the brand reads.

SWAPPING IN AI LATER: everything the pitch needs is passed into generate_pitch()
and a single piece of text (Markdown) comes back out. To use an AI writer later,
write another function that takes the same inputs and returns Markdown, then
change the one line in the app that calls generate_pitch(). Nothing in scoring,
matching or the data files has to change.
"""

from display import clean_name
from matching import AGE_BANDS

# ===========================================================================
# SIGN-OFF: who the pitch is from. Change these to change the last line of
# every pitch. Set the name to "" to leave the sign-off out.
# ===========================================================================
SIGNOFF_NAME = "Aaron Ventura"
SIGNOFF_TITLE = "Partnerships"
# ===========================================================================

# How many activation ideas to show in the pitch.
MAX_ACTIVATIONS = 3

# What to call each type of property inside a sentence ("the tournament's audience").
# Add a line here if you add a new property type.
PROPERTY_NOUN = {
    "premium_tournament": "tournament",
    "challenger_tournament": "tournament",
    "player": "player",
    "university_team": "team",
    "junior_event": "event",
}

# How the category-fit benefit is worded for each type of property. Events are a
# "home" for a brand, a player is an "ambassador", a team is a "partner".
# A property type that is not listed here is worded like an event.
# {subject} is the noun from PROPERTY_NOUN for events and teams ("The tournament"),
# or the property's own name for a player. {label} is the category, such as "luxury watch".
CATEGORY_FIT_STYLE = {
    "premium_tournament": "home",
    "challenger_tournament": "home",
    "junior_event": "home",
    "player": "ambassador",
    "university_team": "partner",
}
CATEGORY_FIT_WORDING = {
    # style: (wording when fit is natural, wording when fit is only good)
    "home": (
        "{subject} is a natural home for {label} brands like yours.",
        "{subject} is a good setting for {label} brands like yours.",
    ),
    "ambassador": (
        "{subject} is a natural ambassador for {label} brands like yours.",
        "{subject} is a good ambassador for {label} brands like yours.",
    ),
    "partner": (
        "{subject} is a natural partner for {label} brands like yours.",
        "{subject} is a good partner for {label} brands like yours.",
    ),
}

# Settings for the "Why this brand" benefits.
CATEGORY_GOOD_FIT = 6        # category fit of 6 or more earns a "good setting" benefit
CATEGORY_NATURAL_FIT = 8     # category fit of 8 or more earns a "natural home" benefit
PURCHASING_POWER_MIN_PCT = 30  # mention purchasing power if at least this share is higher-income
ENGAGEMENT_MIN_PCT = 4       # show the social media engagement rate only if it is at least this (it is a strength)
SIGNIFICANT_SHARE_PCT = 25   # a customer age group counts as "significant" at this share of the audience


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def in_words(number):
    """Write a big number the way a person would say it.
    12,000,000 -> "12 million", 1,234,567 -> "1.2 million", 150,000 -> "150,000"."""
    for size, word in ((1_000_000_000, "billion"), (1_000_000, "million")):
        if number >= size:
            value = round(number / size, 1)
            text = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{text} {word}"
    return f"{number:,}"


def _band_label(part):
    """The age band's name, for example "35–54" (with a proper dash)."""
    for band_part, label in AGE_BANDS:
        if band_part == part:
            return label.replace("-", "–")
    return part


def _lower_first(text):
    """Make the first letter lowercase, unless the first word is an acronym like VIP."""
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


def _activation_ideas(brand, activations, limit):
    """Pick up to `limit` activation ideas for the brand's category from activations.csv."""
    ideas = [row["activation"] for row in activations if row["category"] == brand["category"]]
    return ideas[:limit]


# ---------------------------------------------------------------------------
# "Why this brand": 2 to 3 benefits, written for the brand
# ---------------------------------------------------------------------------
def _audience_benefit(prop, brand, noun):
    """The first benefit: does the audience contain the brand's customers?"""
    # Events with a youth audience: talk about families. Under-18s are never described
    # as the brand's customers, and the brand is never said to get "access to" them.
    if prop.get("audience_includes_minors"):
        return f"The {noun} reaches families: parents and young players together."

    # Otherwise compare the adult age groups only, for the same reason.
    adult_bands = [part for part, _label in AGE_BANDS if part != "under18"]
    property_share = {part: prop[f"age_{part}_pct"] for part in adult_bands}
    brand_share = {part: brand[f"target_age_{part}_pct"] for part in adult_bands}
    core = max(brand_share, key=brand_share.get)  # the brand's biggest adult customer group
    core_label = _band_label(core)

    if property_share[core] == max(property_share.values()):
        return f"Your core customers, aged {core_label}, are the {noun}'s largest audience group."
    if property_share[core] >= SIGNIFICANT_SHARE_PCT:
        return f"Your core customers, aged {core_label}, make up a significant part of the {noun}'s audience."
    # The brand's core group is small here, so point to the age group they share most.
    shared = {part: min(property_share[part], brand_share[part]) for part in adult_bands}
    best = max(shared, key=shared.get)
    return f"The {noun} gives you access to customers aged {_band_label(best)}, one of your key age groups."


def _benefits(prop, match):
    """Return 2-3 plain-English benefits to the brand, built from the data.

    Candidates are listed in priority order and the first three are kept:
    audience, engagement, category fit, purchasing power."""
    brand = match["brand"]
    noun = PROPERTY_NOUN.get(prop["property_type"], prop["property_type"].replace("_", " "))
    candidates = [_audience_benefit(prop, brand, noun)]

    # 2. Engagement: only when it is a strength.
    if prop["engagement_rate_pct"] >= ENGAGEMENT_MIN_PCT:
        candidates.append("A highly engaged following, well above typical engagement rates.")

    # 3. Category: is this a natural setting for the brand's kind of business?
    fit = match["fit"]
    natural_wording, good_wording = CATEGORY_FIT_WORDING[CATEGORY_FIT_STYLE.get(prop["property_type"], "home")]
    # A player is named ("Rising British Player is a natural ambassador..."); events and teams are "The tournament".
    if CATEGORY_FIT_STYLE.get(prop["property_type"]) == "ambassador":
        subject = clean_name(prop["name"])
    else:
        subject = f"The {noun}"
    if fit >= CATEGORY_NATURAL_FIT:
        candidates.append(natural_wording.format(subject=subject, label=match["category_label"]))
    elif fit >= CATEGORY_GOOD_FIT:
        candidates.append(good_wording.format(subject=subject, label=match["category_label"]))

    # 4. Purchasing power.
    if prop["high_income_share_pct"] >= PURCHASING_POWER_MIN_PCT:
        candidates.append(
            f"{prop['high_income_share_pct']}% of the audience is in higher-income brackets, "
            f"giving you a customer base with strong purchasing power."
        )

    benefits = candidates[:3]

    # Always give at least two benefits: fall back to reach.
    if len(benefits) < 2:
        benefits.append(f"Your brand would reach {in_words(prop['annual_audience_reach'])} people a year.")

    return benefits


# ---------------------------------------------------------------------------
# The pitch
# ---------------------------------------------------------------------------
def generate_pitch(prop, match, activations, max_activations=MAX_ACTIVATIONS):
    """Build the pitch as Markdown text.

    prop          one row from properties.csv
    match         one entry from matching.match_brands(...)["matches"]
    activations   the rows of activations.csv
    """
    brand = match["brand"]
    # The word "Placeholder" is hidden from names in the pitch (it stays in the CSVs).
    property_name = clean_name(prop["name"])
    brand_name = clean_name(brand["name"])
    lines = []

    # --- 1. Headline -------------------------------------------------------
    lines.append(f"# Partnership opportunity: {property_name} × {brand_name}")
    lines.append("")
    if prop.get("is_placeholder") or brand.get("is_placeholder"):
        lines.append("> Draft built from placeholder data. All names and figures are invented examples.")
        lines.append("")

    # --- 2. The property ---------------------------------------------------
    lines.append("## The property")
    lines.append("")
    lines.append(f"{prop['description']}.")
    lines.append("")
    # Only strengths are listed. The higher-income share is not repeated here
    # because it already appears in the "Why this brand" benefits.
    lines.append(f"- Annual audience reach: {in_words(prop['annual_audience_reach'])} people")
    if prop["engagement_rate_pct"] >= ENGAGEMENT_MIN_PCT:
        lines.append(f"- Social media engagement rate: {prop['engagement_rate_pct']}%")
    lines.append(f"- Media impressions per year: {in_words(prop['annual_media_impressions'])}")
    lines.append("")

    # --- 3. Why this brand -------------------------------------------------
    lines.append(f"## Why {brand_name}")
    lines.append("")
    for benefit in _benefits(prop, match):
        lines.append(f"- {benefit}")
    lines.append("")

    # --- 4. Activation ideas -----------------------------------------------
    lines.append("## Activation ideas")
    lines.append("")
    ideas = _activation_ideas(brand, activations, max_activations)
    if ideas:
        for number, idea in enumerate(ideas, start=1):
            lines.append(f"{number}. {idea}")
    else:
        lines.append("_No activation ideas listed yet for this category. Add some to activations.csv._")
    lines.append("")

    # --- 5. Next steps -----------------------------------------------------
    lines.append("## Next steps")
    lines.append("")
    if ideas:
        lines.append(
            f"I would like to propose a 30-minute call to walk you through the partnership options, "
            f"starting with the activation ideas above and how they could work for {brand_name}. "
            f"Please let me know a few times that suit you and I will send an invitation."
        )
    else:
        lines.append(
            f"I would like to propose a 30-minute call to walk you through the partnership options "
            f"for {brand_name}. Please let me know a few times that suit you and I will send an invitation."
        )
    lines.append("")

    # --- Sign-off ----------------------------------------------------------
    if SIGNOFF_NAME:
        signoff = f"Prepared by {SIGNOFF_NAME}, {SIGNOFF_TITLE}" if SIGNOFF_TITLE else f"Prepared by {SIGNOFF_NAME}"
        lines.append(signoff)
        lines.append("")

    return "\n".join(lines)
