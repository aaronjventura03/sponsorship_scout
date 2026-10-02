"""Matches a tennis property with the best-fit brands.

How it works, in plain English:
  1. SAFETY RULE FIRST: if the property's audience includes minors, brands
     marked "suitable_for_minors = FALSE" are removed before anything is scored.
     That flag means AGE-RESTRICTED PRODUCTS ONLY (alcohol, gambling and
     similar). A brand that simply does not target children, such as a private
     bank, stays in, because sponsors at junior events often target parents.
  2. Every remaining brand gets a match score out of 100, made of two parts:
       - Audience overlap: how closely the property's age profile matches the
         age profile of the brand's target customers.
       - Category fit: your 0-10 rating from category_fit.csv for this brand
         category and this type of property.
  3. The brands are ranked and the best few are returned, each with
     plain-English reasons explaining why it fits. If two brands have the same
     match score, the one with the higher audience overlap ranks first. If they
     are still exactly level on both, they share a JOINT RANK (shown as "=3")
     and neither is placed ahead because of its position in brands.csv.
     After a joint rank the next rank is skipped: 1, 2, =3, =3, 5.
"""

from display import clean_name

# ===========================================================================
# MATCH SETTINGS - change these to change how matching works
# ===========================================================================
# How much each part counts towards the match score. Only the proportions
# matter: 60/40 behaves exactly like 6/4 or 30/20.
MATCH_WEIGHTS = {
    "audience_overlap": 60,
    "category_fit": 40,
}

# How many brands to return.
TOP_N = 3
# ===========================================================================

# The five age bands, in order: (column name part, label to show on screen).
# In properties.csv the columns are age_<part>_pct, and in brands.csv they are
# target_age_<part>_pct.
AGE_BANDS = [
    ("under18", "under 18"),
    ("18_24", "18-24"),
    ("25_34", "25-34"),
    ("35_54", "35-54"),
    ("55plus", "55 and over"),
]


def _normalise_weights(weights):
    """Rescale the two weights so they add up to 100, keeping proportions."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one match weight must be above zero.")
    return {name: weight * 100 / total for name, weight in weights.items()}


# ---------------------------------------------------------------------------
# Part 1: audience overlap
# ---------------------------------------------------------------------------
def audience_overlap(prop, brand):
    """How much do the property's audience and the brand's target customers overlap?

    For each age band we take the SMALLER of the two percentages, then add the
    five bands up. Two identical age profiles overlap 100%. Two profiles with
    nobody in common overlap 0%.

    Example: the property has 35% aged 35-54 and the brand targets 45% aged
    35-54, so they share 35 percentage points in that band.

    Returns (overlap percentage, shared amount per band).
    """
    shared = {}
    for part, _label in AGE_BANDS:
        property_share = prop[f"age_{part}_pct"]
        brand_share = brand[f"target_age_{part}_pct"]
        shared[part] = min(property_share, brand_share)
    return sum(shared.values()), shared


# ---------------------------------------------------------------------------
# Part 2: category fit
# ---------------------------------------------------------------------------
def _category_row(brand, category_fit_rows):
    """Find this brand's category row in category_fit.csv."""
    for row in category_fit_rows:
        if row["category"] == brand["category"]:
            return row
    raise ValueError(
        f"category_fit.csv has no row for brand category '{brand['category']}' "
        f"(brand: {brand['name']}). Add a row for it."
    )


def category_fit_score(brand, prop, category_fit_rows):
    """Look up your 0-10 category fit rating in category_fit.csv.
    Rows are brand categories; columns are property types."""
    property_type = prop["property_type"]
    row = _category_row(brand, category_fit_rows)
    if property_type not in row:
        raise ValueError(
            f"category_fit.csv has no column for property type '{property_type}'. "
            f"Add one, or fix the type in properties.csv."
        )
    return row[property_type]


def category_label(brand, category_fit_rows):
    """The friendly name for a brand's category (the category_label column in
    category_fit.csv). If it is missing, tidy up the category name instead."""
    row = _category_row(brand, category_fit_rows)
    return row.get("category_label") or _nice(brand["category"])


def _suits_phrase(score):
    """A plain-English ending for a 0-10 category fit score, as in
    "brands suit a premium tournament well"."""
    if score >= 8:
        return "well"
    if score >= 6:
        return "reasonably well"
    if score >= 4:
        return "only moderately well"
    return "poorly"


def _with_article(text):
    """Put 'a' or 'an' in front of a word: 'a premium tournament', 'an elite event'."""
    return f"an {text}" if text[0].lower() in "aeio" else f"a {text}"


def _overlap_word(percent):
    """A plain-English word for an audience overlap percentage."""
    if percent >= 70:
        return "strong"
    if percent >= 50:
        return "reasonable"
    return "limited"


def _nice(text):
    """Turn a CSV name like 'luxury_watches' into 'luxury watches'."""
    return text.replace("_", " ")


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------
def explain_match(prop, brand, overlap_pct, shared, fit, label):
    """Return a list of plain-English reasons why this brand fits this property.
    `label` is the friendly category name, such as "luxury watch"."""
    # The age band where the two audiences overlap most.
    best_part, best_label = max(AGE_BANDS, key=lambda band: shared[band[0]])

    return [
        (
            f"Audience overlap is {_overlap_word(overlap_pct)} ({overlap_pct:.0f}%). "
            f"The biggest shared group is {best_label}: "
            f"{prop[f'age_{best_part}_pct']}% of the property's audience and "
            f"{brand[f'target_age_{best_part}_pct']}% of the brand's target customers."
        ),
        (
            f"Category fit {fit}/10: {label} brands suit "
            f"{_with_article(_nice(prop['property_type']))} {_suits_phrase(fit)}."
        ),
        f"UK link: {brand['uk_link']}.",
    ]


def joint_first(matches):
    """If two or more brands share first place, return them; otherwise return
    an empty list. The app uses this to make the user choose which brand the
    pitch is written for."""
    first_place = [match for match in matches if match["rank"] == 1]
    return first_place if len(first_place) > 1 else []


# ---------------------------------------------------------------------------
# The main function
# ---------------------------------------------------------------------------
def match_brands(prop, brands, category_fit_rows, top_n=TOP_N, weights=None):
    """Find the best-fit brands for one property.

    Returns a dictionary with:
      "matches"  - the brands ranked 1 to top_n, best first. Each one has its
                   "rank" (a number) and "rank_label" (for example "2" or "=3"),
                   its "total" score out of 100, the "overlap_pct" and "fit"
                   behind it, the points each part contributed, and a list of
                   "reasons". If brands share the last rank, all of them are
                   included, so you can get more than top_n back.
      "excluded" - brands removed by the safety rule, each with a reason.
    """
    weights = _normalise_weights(weights or MATCH_WEIGHTS)

    # Step 1: the safety rule.
    excluded = []
    candidates = []
    for brand in brands:
        if prop["audience_includes_minors"] and not brand["suitable_for_minors"]:
            excluded.append({
                "brand": brand,
                "reason": f"{clean_name(brand['name'])} sells an age-restricted product, so it is removed for events with a youth audience.",
            })
        else:
            candidates.append(brand)

    # Step 2: score every remaining brand.
    matches = []
    for brand in candidates:
        overlap_pct, shared = audience_overlap(prop, brand)
        fit = category_fit_score(brand, prop, category_fit_rows)

        # Each part is turned into a 0-1 share, then multiplied by its weight.
        overlap_points = overlap_pct / 100 * weights["audience_overlap"]
        fit_points = fit / 10 * weights["category_fit"]

        label = category_label(brand, category_fit_rows)
        matches.append({
            "brand": brand,
            "category_label": label,
            "total": overlap_points + fit_points,
            "overlap_pct": overlap_pct,
            "overlap_points": overlap_points,
            "fit": fit,
            "fit_points": fit_points,
            "reasons": explain_match(prop, brand, overlap_pct, shared, fit, label),
        })

    # Step 3: best first. A tie on the total score is broken by the higher
    # audience overlap. (The total is rounded first so that tiny computer
    # rounding differences do not hide a genuine tie.)
    def sort_key(match):
        return (round(match["total"], 6), match["overlap_pct"])

    matches.sort(key=sort_key, reverse=True)

    # Step 4: give out ranks. Brands exactly level on both the score and the
    # overlap share a rank, and the next rank after them is skipped.
    for position, match in enumerate(matches):
        if position > 0 and sort_key(match) == sort_key(matches[position - 1]):
            match["rank"] = matches[position - 1]["rank"]
        else:
            match["rank"] = position + 1
    for match in matches:
        shared = sum(1 for other in matches if other["rank"] == match["rank"])
        match["rank_label"] = f"={match['rank']}" if shared > 1 else str(match["rank"])

    # Keep everyone ranked within the top few (so a brand tied for the last
    # place is not dropped because of where it sits in the file).
    return {"matches": [m for m in matches if m["rank"] <= top_n], "excluded": excluded}
