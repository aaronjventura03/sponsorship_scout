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
from scoring import broadcast_description, engagement_is_measurable

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
ENGAGEMENT_MIN_PER_POST = 100  # the "highly engaged" benefit also needs at least this many engagements per post
BROADCAST_MIN_TIER = 4       # show the broadcast coverage line only if the broadcast tier is at least this
# Property types whose "audience" is Instagram followers rather than people reached at an event.
FOLLOWER_TYPES = {"player"}
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


def _is_estimate(prop, figure):
    """Is this figure an estimate (rather than published or calculated)?
    `figure` is the start of its column name, such as "audience" or "high_income"."""
    return prop.get(f"{figure}_confidence") == "estimate"


def _approximately(prop, figure, text):
    """Put "about" in front of a figure that is only an estimate, so the pitch
    never presents a guess as a fact: "3,000" becomes "about 3,000"."""
    return f"about {text}" if _is_estimate(prop, figure) else text


def _engagement_rate_is_strong(prop):
    """Could engagement be measured, and is the engagement RATE high enough?
    (The rate is what a brand understands; the app scores engagements per post.)
    This is only half of the test in _engagement_is_strong below."""
    rate = prop.get("engagement_rate_pct")
    return engagement_is_measurable(prop) and isinstance(rate, (int, float)) and rate >= ENGAGEMENT_MIN_PCT


def _engagement_is_strong(prop):
    """Is engagement strong enough to show the engagement rate, or to claim "a highly
    engaged following"? Both use this test.
    It needs BOTH a strong rate AND a real volume of engagement: a high rate on its
    own can come from a tiny account, so at least ENGAGEMENT_MIN_PER_POST engagements
    per post are required as well."""
    per_post = prop.get("engagement_per_post")
    return _engagement_rate_is_strong(prop) and isinstance(per_post, (int, float)) and per_post >= ENGAGEMENT_MIN_PER_POST


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
def _age_profile_is_estimate(prop):
    """Is the property's audience age profile only an estimate? (Properties with no
    confidence label are treated as having a firm profile.)"""
    return prop.get("age_profile_confidence") == "estimate"


def _audience_benefit(prop, brand, noun):
    """The first benefit: does the audience contain the brand's customers?

    These claims come from the property's audience age profile. Where that profile is
    only an estimate, the wording is softened ("are likely the ... largest audience
    group") so the pitch never states a guess as a fact."""
    estimated = _age_profile_is_estimate(prop)
    likely = " likely" if estimated else ""            # "are likely the largest ..."

    # Events with a youth audience: talk about families. Under-18s are never described
    # as the brand's customers, and the brand is never said to get "access to" them.
    # This is a statement about the kind of event, not about the estimated age profile,
    # so it is stated plainly and never hedged.
    if prop.get("audience_includes_minors"):
        return f"The {noun} reaches families: parents and young players together."

    # Otherwise compare the adult age groups only, for the same reason.
    adult_bands = [part for part, _label in AGE_BANDS if part != "under18"]
    property_share = {part: prop[f"age_{part}_pct"] for part in adult_bands}
    brand_share = {part: brand[f"target_age_{part}_pct"] for part in adult_bands}
    core = max(brand_share, key=brand_share.get)  # the brand's biggest adult customer group
    core_label = _band_label(core)

    if property_share[core] == max(property_share.values()):
        return f"Your core customers, aged {core_label}, are{likely} the {noun}'s largest audience group."
    if property_share[core] >= SIGNIFICANT_SHARE_PCT:
        verb = "are likely to make up" if estimated else "make up"
        return f"Your core customers, aged {core_label}, {verb} a significant part of the {noun}'s audience."
    # The brand's core group is small here, so point to the age group they share most.
    shared = {part: min(property_share[part], brand_share[part]) for part in adult_bands}
    best = max(shared, key=shared.get)
    verb = "is likely to give" if estimated else "gives"
    return f"The {noun} {verb} you access to customers aged {_band_label(best)}, one of your key age groups."


def _benefits(prop, match):
    """Return 2-3 plain-English benefits to the brand, built from the data.

    Candidates are listed in priority order and the first three are kept:
    audience, engagement, category fit, purchasing power."""
    brand = match["brand"]
    noun = PROPERTY_NOUN.get(prop["property_type"], prop["property_type"].replace("_", " "))
    candidates = [_audience_benefit(prop, brand, noun)]

    # 2. Engagement: only when it could be measured and is a strength.
    if _engagement_is_strong(prop):
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

    # 4. Purchasing power. An estimated share is introduced as "An estimated ...".
    if prop["high_income_share_pct"] >= PURCHASING_POWER_MIN_PCT:
        opening = "An estimated" if _is_estimate(prop, "high_income") else ""
        share = f"{prop['high_income_share_pct']}% of the audience is in higher-income brackets"
        sentence = f"{opening} {share}" if opening else share
        candidates.append(f"{sentence}, giving you a customer base with strong purchasing power.")

    benefits = candidates[:3]

    # Always give at least two benefits: fall back to reach.
    if len(benefits) < 2:
        reach = _approximately(prop, "audience", in_words(prop["annual_audience_reach"]))
        if prop["property_type"] in FOLLOWER_TYPES:
            benefits.append(f"Your brand would reach {reach} followers.")
        else:
            benefits.append(f"Your brand would reach {reach} people.")

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
    if prop.get("is_placeholder"):
        lines.append("> Draft built from placeholder data. All names and figures are invented examples.")
        lines.append("")
    elif brand.get("is_placeholder"):
        lines.append(
            "> Illustrative draft. The brand shown is an example of its category, not a real company, "
            "and this is not a real proposal."
        )
        lines.append("")

    # --- 2. The property ---------------------------------------------------
    lines.append("## The property")
    lines.append("")
    lines.append(f"{prop['description']}.")
    lines.append("")
    # Only strengths are listed. The higher-income share is not repeated here
    # because it already appears in the "Why this brand" benefits.
    audience = _approximately(prop, "audience", in_words(prop["annual_audience_reach"]))
    if prop["property_type"] in FOLLOWER_TYPES:
        lines.append(f"- Instagram followers: {audience}")
    else:
        lines.append(f"- Audience reach: {audience} people")
    if _engagement_is_strong(prop):  # the same two-part test as the "highly engaged" benefit
        lines.append(f"- Social media engagement rate: {prop['engagement_rate_pct']}%")
    if prop["broadcast_tier"] >= BROADCAST_MIN_TIER:
        lines.append(f"- Broadcast coverage: {broadcast_description(prop['broadcast_tier'])}")
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
