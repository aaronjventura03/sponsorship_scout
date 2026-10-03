"""Sponsorship Scout: the web app.

Run it from the sponsorship_scout folder with:
    .venv/bin/streamlit run app.py

How the page is laid out:
  Sidebar     pick a property and adjust the score weights
  Top         a ranking table of every property (updates as the sliders move)
  Analysis    the chosen property's score breakdown and its top brand matches
  Pitch       choose a brand, read the brand-facing pitch, download it

Streamlit re-runs this whole file from the top every time you click or drag
something, so the page always reflects the current choices. All the real work
(scoring, matching, pitch writing) happens in the other .py files.
"""

from datetime import date

import pandas as pd  # installed together with Streamlit; used here to tint the chosen row
import streamlit as st

from data_loader import load_activations, load_brands, load_category_fit, load_properties
from display import clean_name, type_label
from matching import MATCH_WEIGHTS, joint_first, match_brands
from pitch import FOLLOWER_TYPES, generate_pitch, in_words
from scoring import (
    CONFIDENCE_COLUMN,
    DEFAULT_WEIGHTS,
    FACTOR_LABELS,
    broadcast_description,
    engagement_is_measurable,
    normalise_weights,
    rank_labels,
    rank_properties,
    score_property,
)

st.set_page_config(page_title="Sponsorship Scout", page_icon="🎾", layout="wide")

# Streamlit adds a small link icon beside every heading. Hide them across the whole page.
st.html('<style>[data-testid="stHeaderActionElements"] { display: none; }</style>')

# The CSV files are small, so they are read afresh each time. Edit a file,
# refresh the page, and the change shows up.
properties = load_properties()
brands = load_brands()
category_fit = load_category_fit()
activations = load_activations()


def demote_headings(markdown):
    """Make the pitch's headings smaller on screen so it reads like a document:
    '# Title' becomes '### Title' and '## Section' becomes '#### Section'.
    Only the on-screen copy changes. The downloaded file keeps the original headings."""
    lines = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            line = "##" + line
        elif line.startswith("# "):
            line = "###" + line[1:]
        lines.append(line)
    return "\n".join(lines)


def format_weight(weight):
    """Show 25 as '25' and 33.33 as '33.3'."""
    return f"{weight:.0f}" if round(weight, 1) == round(weight) else f"{weight:.1f}"


def reset_weights():
    """Put every slider back to its default weight."""
    for factor, weight in DEFAULT_WEIGHTS.items():
        st.session_state[f"weight_{factor}"] = weight


# ===========================================================================
# Title and placeholder warning (always visible)
# ===========================================================================
st.title("🎾 Sponsorship Scout")
st.caption("Score a tennis property, find its best-fit brands and draft a partnership pitch.")

collected = max((p["date_collected"] for p in properties if p.get("date_collected")), default=None)
collected_text = f"{date.fromisoformat(collected).day} {date.fromisoformat(collected):%B %Y}" if collected else "an unknown date"

if any(p.get("is_placeholder") for p in properties):
    st.warning(
        "**PLACEHOLDER DATA.** Some properties in this app are invented examples, not real research. "
        "Replace the CSV files in the data folder with real figures before relying on any result."
    )
elif any(b.get("is_placeholder") for b in brands):
    st.warning(
        f"**Real properties, illustrative brands.** The properties are real, with sourced or estimated figures "
        f"as of {collected_text} (the Analysis section shows how confident each figure is). "
        "The brands are illustrative categories, not real companies, and the pitches are illustrative only, "
        "not real proposals."
    )

# ===========================================================================
# Sidebar: property picker and weight sliders
# ===========================================================================
with st.sidebar:
    st.header("Property")
    names = [clean_name(p["name"]) for p in properties]  # "Placeholder" is hidden from displayed names
    chosen = properties[names.index(st.selectbox("Choose a tennis property", names))]

    st.header("Score weights")
    st.caption(
        "Drag to change how much each factor counts towards the score. "
        "The weights are always rescaled to total 100, so the score stays out of 100."
    )
    for factor, label in FACTOR_LABELS.items():
        st.session_state.setdefault(f"weight_{factor}", DEFAULT_WEIGHTS[factor])
        st.slider(label, min_value=0, max_value=100, key=f"weight_{factor}")
    st.button("Reset to defaults", on_click=reset_weights)

    slider_weights = {factor: st.session_state[f"weight_{factor}"] for factor in FACTOR_LABELS}
    if sum(slider_weights.values()) == 0:
        st.error("Set at least one weight above zero. Using the defaults for now.")
        weights = normalise_weights(DEFAULT_WEIGHTS)
    else:
        weights = normalise_weights(slider_weights)

    st.caption(
        "**Weights in use (total 100):** "
        + " · ".join(f"{FACTOR_LABELS[f]} {format_weight(w)}" for f, w in weights.items())
    )

# ===========================================================================
# Top: ranking table of all properties
# ===========================================================================
st.header("Property ranking")
st.caption("Commercial value out of 100. The table updates as you move the sliders.")

ranked = rank_properties(properties, weights)
labels = rank_labels([result["total"] for _, result in ranked])

# The ranking shows only the headline numbers. The factor-by-factor breakdown
# for the chosen property is in the Analysis section below.
table = [
    {
        "Rank": label,
        "Property": clean_name(prop["name"]),
        "Type": type_label(prop["property_type"]),
        "Score": result["total"],
    }
    for label, (prop, result) in zip(labels, ranked)
]
def highlight_chosen(row):
    """Give the chosen property's row a soft tinted background."""
    tint = "background-color: rgba(255, 75, 75, 0.18)" if row["Property"] == clean_name(chosen["name"]) else ""
    return [tint] * len(row)


st.dataframe(
    pd.DataFrame(table).style.apply(highlight_chosen, axis=1),
    hide_index=True,
    width="stretch",
    column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f")},
)

# ===========================================================================
# Analysis for the chosen property
# ===========================================================================
st.divider()
st.header("Analysis")
st.markdown(f"**{clean_name(chosen['name'])}** · {type_label(chosen['property_type'])}")

# --- Score breakdown -------------------------------------------------------
result = score_property(chosen, weights)
st.subheader("Commercial score")
st.metric("Out of 100", f"{result['total']:.1f}")

# How to show each raw figure from properties.csv in plain words.
if chosen["property_type"] in FOLLOWER_TYPES:
    audience_figure = f"{chosen['annual_audience_reach']:,} Instagram followers"
else:
    audience_figure = f"{in_words(chosen['annual_audience_reach'])} people"
if engagement_is_measurable(chosen):
    # Scored on engagements per post. The rate is shown as context only.
    engagement_figure = f"{chosen['engagement_per_post']:,} per post (median likes + comments)"
    if isinstance(chosen.get("engagement_rate_pct"), (int, float)):
        engagement_figure += f" · rate {chosen['engagement_rate_pct']}% of {chosen['engagement_followers']:,} followers"
else:
    engagement_figure = "Not measurable (no dedicated account)"
raw_figures = {
    "audience": audience_figure,
    "engagement": engagement_figure,
    "demographics": f"{chosen['high_income_share_pct']}% higher-income",
    "media": f"Tier {chosen['broadcast_tier']}: {broadcast_description(chosen['broadcast_tier'])}",
    "prestige": f"{chosen['prestige_rating']} out of 10",
}
# If a factor could not be measured, say so clearly and explain what happened to its weight.
if result["unmeasured"]:
    left_out = ", ".join(
        f"{FACTOR_LABELS[factor]} (weight {format_weight(result['factors'][factor]['set_weight'])})"
        for factor in result["unmeasured"]
    )
    st.info(
        f"**Not measured: {left_out}.** This could not be measured for "
        f"{clean_name(chosen['name'])}, so its weight has been shared across the other factors in proportion "
        "to their weights. The score reflects measured evidence only, and is still out of 100."
    )

rows = []
for factor, item in result["factors"].items():
    row = {
        "Factor": FACTOR_LABELS[factor],
        "Figure": raw_figures[factor],
        "Confidence": item["confidence"].capitalize(),
        "Score (0-10)": None if item["score"] is None else round(item["score"], 1),
    }
    if result["unmeasured"]:
        row["Weight set"] = round(item["set_weight"], 1)  # what the sliders say
    row["Weight"] = round(item["weight"], 1)  # what was actually used
    row["Points"] = round(item["points"], 1)
    rows.append(row)

st.dataframe(
    rows,
    hide_index=True,
    width="stretch",
    column_config={
        "Score (0-10)": st.column_config.NumberColumn(format="%.1f"),
        "Weight set": st.column_config.NumberColumn(format="%.1f"),
        "Weight": st.column_config.NumberColumn(format="%.1f"),
        "Points": st.column_config.NumberColumn(format="%.1f"),
    },
)
st.caption(
    "Confidence: **Published** = a published figure. **Calculated** = worked out from published figures or posts. "
    "**Estimate** = a judgement, so treat it with care. **Not measured** = could not be measured, so it is "
    "left out of the score. Engagement is scored on engagements per post, not on the rate, "
    "because a rate flatters small accounts."
)

# Where each figure came from. Collapsed by default to keep the page tidy.
with st.expander(f"Data sources (collected {chosen.get('date_collected', 'unknown date')})"):
    source_rows = []
    for factor, column in CONFIDENCE_COLUMN.items():
        prefix = column.removesuffix("_confidence")
        source_rows.append({
            "Figure": FACTOR_LABELS[factor],
            "Source": chosen.get(f"{prefix}_source", "") or "(none recorded)",
            "Confidence": result["factors"][factor]["confidence"].capitalize(),
            "Link": chosen.get(f"{prefix}_source_url", "") or None,
        })
    source_rows.append({
        "Figure": "Audience age profile (used in matching)",
        "Source": chosen.get("age_profile_source", "") or "(none recorded)",
        "Confidence": str(chosen.get("age_profile_confidence", "")).capitalize(),
        "Link": None,
    })
    st.dataframe(
        source_rows,
        hide_index=True,
        width="stretch",
        column_config={"Link": st.column_config.LinkColumn("Link")},
    )

# --- Brand matches ---------------------------------------------------------
outcome = match_brands(chosen, brands, category_fit)
matches = outcome["matches"]

st.subheader("Top brand matches")
match_total = sum(MATCH_WEIGHTS.values())
st.caption(
    f"Match score combines audience overlap ({MATCH_WEIGHTS['audience_overlap'] / match_total:.0%}) "
    f"and category fit ({MATCH_WEIGHTS['category_fit'] / match_total:.0%}). "
    "Brands marked '=' are tied."
)
if str(chosen.get("age_profile_confidence", "")).lower() == "estimate":
    st.caption(
        "Matching uses the property's audience age profile, which is currently an estimate "
        "(not yet researched), so treat the audience-overlap figures with care."
    )
for match in matches:
    with st.container(border=True):
        st.markdown(f"**{match['rank_label']}. {clean_name(match['brand']['name'])}** · match score **{match['total']:.1f} / 100**")
        st.caption(
            f"Audience overlap {match['overlap_pct']:.0f}% = {match['overlap_points']:.1f} points · "
            f"Category fit {match['fit']}/10 = {match['fit_points']:.1f} points"
        )
        for reason in match["reasons"]:
            st.markdown(f"- {reason}")

if outcome["excluded"]:
    with st.expander("Brands removed by the youth-audience rule"):
        for item in outcome["excluded"]:
            st.markdown(f"- {item['reason']}")

# ===========================================================================
# Pitch
# ===========================================================================
st.divider()
st.header("Pitch")

brand_names = {match["brand"]["id"]: match for match in matches}
brand_ids = list(brand_names)
tied_for_first = joint_first(matches)

if tied_for_first:
    st.warning(
        f"{' and '.join(clean_name(m['brand']['name']) for m in tied_for_first)} share first place. "
        "Choose which brand to write the pitch for."
    )

# The widget's key includes the brand list, so the choice resets if the list changes
# (for example after moving a slider reorders the matches).
chosen_brand_id = st.selectbox(
    "Brand for the pitch",
    brand_ids,
    index=None if tied_for_first else 0,  # no default when there is a joint first
    format_func=lambda brand_id: f"{brand_names[brand_id]['rank_label']}. {clean_name(brand_names[brand_id]['brand']['name'])}",
    placeholder="Choose a brand",
    key=f"pitch_brand_{chosen['id']}_{'_'.join(brand_ids)}",
)

if chosen_brand_id is not None:
    pitch_text = generate_pitch(chosen, brand_names[chosen_brand_id], activations)
    with st.container(border=True):
        st.markdown(demote_headings(pitch_text))  # smaller headings on screen; the download is unchanged
    st.download_button(
        "Download pitch (Markdown)",
        data=pitch_text,
        file_name=f"pitch_{chosen['id']}_{chosen_brand_id}.md",
        mime="text/markdown",
    )
