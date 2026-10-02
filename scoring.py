"""Commercial value score (out of 100) for a tennis property.

How it works, in plain English:
  1. Each of five factors is turned into a score from 0 to 10.
  2. Each factor has a weight. The weights add up to 100.
  3. A factor's points = (its 0-10 score / 10) x its weight.
  4. The total score is the sum of the five factors' points.

So a property scoring 10/10 on everything would get exactly 100.
"""

import math

# ---------------------------------------------------------------------------
# WEIGHTS: how much each factor counts towards the 100 points.
# ---------------------------------------------------------------------------
# Prestige is weighted lowest on purpose. A prestigious event usually already
# has a big audience and lots of media coverage, so counting prestige heavily
# would reward the same thing twice.
#
# Demographics is purchasing power ONLY (share of the audience in higher-income
# brackets). Age is deliberately left out here: a young or older audience is not
# "worth less", it simply suits different brands. Age fit is handled later, in
# brand matching.
DEFAULT_WEIGHTS = {
    "audience": 25,
    "engagement": 20,
    "demographics": 20,
    "media": 20,
    "prestige": 15,
}

# Friendly names for showing the breakdown on screen.
FACTOR_LABELS = {
    "audience": "Audience size",
    "engagement": "Social engagement",
    "demographics": "Purchasing power",
    "media": "Media exposure",
    "prestige": "Prestige",
}

# ---------------------------------------------------------------------------
# SCALES: what number earns 0 out of 10, and what earns 10 out of 10.
# Change these if you think a scale is too harsh or too generous.
# ---------------------------------------------------------------------------
# Audience and media use a LOG scale. On a normal scale, a 12 million audience
# would make a 600,000 audience look like nothing. On a log scale, each
# multiplication by 10 adds the same number of points, so a small event can
# still score meaningfully next to a huge one.
AUDIENCE_FLOOR = 1_000             # this audience or lower = 0 / 10
AUDIENCE_CEILING = 20_000_000      # this audience or higher = 10 / 10

MEDIA_FLOOR = 100_000              # this many media impressions or fewer = 0 / 10
MEDIA_CEILING = 500_000_000        # this many or more = 10 / 10

# Engagement and purchasing power use a simple straight-line scale from 0.
ENGAGEMENT_CEILING_PCT = 8         # an 8% social engagement rate or higher = 10 / 10
HIGH_INCOME_CEILING_PCT = 50       # 50% or more of the audience in higher-income brackets = 10 / 10


# ---------------------------------------------------------------------------
# Helpers that turn a raw number into a 0-10 score
# ---------------------------------------------------------------------------
def _clamp(score):
    """Keep a score between 0 and 10."""
    return max(0.0, min(10.0, score))


def log_scale(value, floor, ceiling):
    """0-10 score on a log scale between a floor (0) and a ceiling (10)."""
    if value <= floor:
        return 0.0
    position = (math.log10(value) - math.log10(floor)) / (math.log10(ceiling) - math.log10(floor))
    return _clamp(position * 10)


def straight_line_scale(value, ceiling):
    """0-10 score on a straight line: 0 earns 0, the ceiling earns 10."""
    return _clamp(value / ceiling * 10)


# ---------------------------------------------------------------------------
# The five factor scores (each 0-10)
# ---------------------------------------------------------------------------
def factor_scores(prop):
    """Turn one property's raw numbers into five scores, each out of 10.
    `prop` is one row from properties.csv."""
    return {
        "audience": log_scale(prop["annual_audience_reach"], AUDIENCE_FLOOR, AUDIENCE_CEILING),
        "engagement": straight_line_scale(prop["engagement_rate_pct"], ENGAGEMENT_CEILING_PCT),
        "demographics": straight_line_scale(prop["high_income_share_pct"], HIGH_INCOME_CEILING_PCT),
        "media": log_scale(prop["annual_media_impressions"], MEDIA_FLOOR, MEDIA_CEILING),
        # Prestige is your own 1-10 rating, so it is used as it stands.
        "prestige": _clamp(prop["prestige_rating"]),
    }


# ---------------------------------------------------------------------------
# Weights and the final score
# ---------------------------------------------------------------------------
def normalise_weights(weights):
    """Rescale weights so they add up to exactly 100, keeping their proportions.
    This is what keeps the score 'out of 100' when sliders are moved later.
    Example: {a: 50, b: 50, c: 100} becomes {a: 25, b: 25, c: 50}."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one weight must be above zero.")
    return {factor: weight * 100 / total for factor, weight in weights.items()}


def score_property(prop, weights=None):
    """Score one property. Returns a dictionary with:
      "total"   - the score out of 100
      "factors" - for each factor: its 0-10 "score", its "weight" and the
                  "points" it contributed to the total
    """
    weights = normalise_weights(weights or DEFAULT_WEIGHTS)
    scores = factor_scores(prop)

    factors = {}
    for factor, score in scores.items():
        factors[factor] = {
            "score": score,
            "weight": weights[factor],
            "points": score / 10 * weights[factor],
        }

    total = sum(item["points"] for item in factors.values())
    return {"total": total, "factors": factors}


def rank_labels(totals):
    """Rank labels for a list of scores that is already ordered best first.
    Equal scores share a rank, shown with "=", and the next rank is skipped:
    [90, 80, 70, 70, 50] gives ["1", "2", "=3", "=3", "5"]."""
    keys = [round(total, 6) for total in totals]  # rounding hides tiny computer errors
    ranks = [keys.index(key) + 1 for key in keys]  # the first position holding this score
    return [f"={rank}" if ranks.count(rank) > 1 else str(rank) for rank in ranks]


def rank_properties(properties, weights=None):
    """Score every property and return them best first, as a list of
    (property, result) pairs."""
    scored = [(prop, score_property(prop, weights)) for prop in properties]
    return sorted(scored, key=lambda pair: pair[1]["total"], reverse=True)
