"""The "Look up on Wikipedia" section of the app.

The flow, in plain English:
  1. You type a name and press "Search Wikipedia". The best few matching pages are listed.
  2. You pick the right page and press "Use this page". The app fetches its summary, facts
     and monthly page views, and shows each one with a link to its source.
  3. A form appears, pre-filled with what Wikipedia gave us. You add or correct the other
     figures and mark each one Sourced or Estimated.
  4. "Score this property" adds it to the property picker, the ranking, the analysis and
     the pitch. It is kept for this browser session only.

Streamlit re-runs the whole page every time something is clicked. So searches and page
fetches happen only inside button callbacks (never on a plain re-run), and their results
are kept in st.session_state. That way Wikipedia is contacted once per click, not once
per re-run.
"""

from datetime import date

import pandas as pd
import streamlit as st

import custom_property
import wikipedia_lookup as wiki
from display import property_label, type_label
from matching import AGE_BANDS
from scoring import BROADCAST_RUBRIC


# ---------------------------------------------------------------------------
# Button callbacks. Streamlit runs these just before it re-runs the page.
# ---------------------------------------------------------------------------
def _search():
    """Search Wikipedia for the name that was typed."""
    state = st.session_state
    state["wiki_error"], state["wiki_page"], state["wiki_scored"], state["wiki_form_errors"] = "", None, "", []
    state.pop("wiki_pick", None)  # the old list of results no longer applies
    try:
        state["wiki_results"] = wiki.search(state.get("wiki_query", ""))
    except wiki.WikipediaError as problem:
        state["wiki_results"] = None
        state["wiki_error"] = str(problem)


def _use_page():
    """Fetch the summary, facts and page views for the page that was picked."""
    state = st.session_state
    state["wiki_error"], state["wiki_scored"], state["wiki_form_errors"] = "", "", []
    try:
        state["wiki_page"] = wiki.lookup_page(state["wiki_pick"])
    except wiki.WikipediaError as problem:
        state["wiki_page"] = None
        state["wiki_error"] = str(problem)


def _read_form():
    """Collect what the user entered in the form into the dictionary custom_property expects."""
    state = st.session_state
    prefix, page, types = state["wiki_form_prefix"], state["wiki_page"], state["wiki_types"]

    def read(name):
        return state.get(prefix + name)

    def basis(name):
        return custom_property.SOURCED if read(name) == "Sourced" else custom_property.ESTIMATED

    ptype = state.get(f"wf_type|{page['title']}")
    values = custom_property.default_values(page, types, chosen_type=ptype)  # for the description
    values.update({
        "name": read("name"),
        "property_type": ptype,
        "audience_includes_minors": bool(read("minors")),
        "engagement_rate_pct": read("rate"),
        "engagement_account": read("account") or "",
        "engagement_followers": read("followers"),
        "age_profile": {part: read(f"age_{part}") for part, _label in AGE_BANDS},
        "age_mode": basis("age_mode"),
        "age_source": read("age_source") or "",
    })
    values["figures"] = {
        factor: {
            "value": read(f"{factor}_value"),
            "mode": basis(f"{factor}_mode"),
            "source": read(f"{factor}_source") or "",
            "url": read(f"{factor}_url") or "",
        }
        for factor in custom_property.FIGURES
    }
    return values


def _score():
    """Check the form. If it is fine, add the property to the session and select it."""
    state = st.session_state
    prop, errors = custom_property.build_property(_read_form())
    state["wiki_form_errors"] = errors
    if prop is None:
        state["wiki_scored"] = ""
        return
    label = property_label(prop)
    state.setdefault("custom_properties", {})[label] = prop
    state["property_choice"] = label  # the sidebar picker now shows the new property
    state["wiki_scored"] = label


def _remove_lookups():
    st.session_state["custom_properties"] = {}
    st.session_state.pop("property_choice", None)  # back to the first saved property
    st.session_state["wiki_scored"] = ""


# ---------------------------------------------------------------------------
# What Wikipedia gave us
# ---------------------------------------------------------------------------
def _render_page(page):
    """Show the summary, the page views and the facts, each with its source link."""
    st.subheader(page["title"])
    if page["description"]:
        st.caption(page["description"])
    for note in page["notes"]:
        st.warning(note)
    if page["extract"]:
        st.markdown(page["extract"])
    st.caption(
        f"Source: [{page['url']}]({page['url']}) · Wikipedia text is shared under the "
        f"[{wiki.LICENCE_NAME}]({wiki.LICENCE_URL}) licence."
    )
    if page["type"] == "disambiguation":
        return

    rows = [{"Figure": "Page summary", "Value": (page["extract"][:90] + "...") if len(page["extract"]) > 90 else page["extract"] or "-", "Source": page["url"]}]
    views = page["pageviews"]
    if views:
        rows.append({"Figure": "Monthly page views (12-month average)", "Value": f"{views['average_monthly']:,}", "Source": views["source_url"]})
        rows.append({"Figure": "Page views in a year (average x 12)", "Value": f"{views['annual_estimate']:,}", "Source": views["source_url"]})
    rows += [{"Figure": fact["label"], "Value": fact["value"], "Source": fact["source_url"]} for fact in page["facts"]]

    st.markdown("**What Wikipedia gave us** (every figure links to its source)")
    st.dataframe(rows, hide_index=True, width="stretch", column_config={"Source": st.column_config.LinkColumn("Source")})
    if views:
        st.caption(f"Monthly page views, last {len(views['months'])} complete months (Wikimedia): a measure of public interest")
        st.bar_chart(pd.DataFrame({"Page views": [m["views"] for m in views["months"]]}, index=[m["month"] for m in views["months"]]))


# ---------------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------------
def _figure_row(prefix, factor, spec, entry, first):
    """One row of the form: a value, Sourced/Estimated, a source note and an optional link."""
    columns = st.columns([2, 2, 3, 3])
    hidden = "visible" if first else "collapsed"
    integer = spec["whole"]
    kwargs = {
        "min_value": int(spec["low"]) if integer else float(spec["low"]),
        "value": None if entry["value"] is None else (int(entry["value"]) if integer else float(entry["value"])),
        "step": 1 if integer else 0.5,
        "key": prefix + f"{factor}_value",
    }
    if spec["high"] is not None:
        kwargs["max_value"] = int(spec["high"]) if integer else float(spec["high"])
    if factor == "media":
        kwargs["help"] = "Rubric: " + "; ".join(f"{tier}+ = {text}" for tier, text in BROADCAST_RUBRIC)
    columns[0].number_input(spec["label"], **kwargs)
    columns[1].radio(
        "Sourced or estimated?", ["Sourced", "Estimated"], index=0 if entry["mode"] == custom_property.SOURCED else 1,
        horizontal=True, key=prefix + f"{factor}_mode", label_visibility=hidden,
    )
    columns[2].text_input("Source note", value=entry["source"], key=prefix + f"{factor}_source",
                          placeholder="Where does this come from?", label_visibility=hidden)
    columns[3].text_input("Link (optional)", value=entry["url"], key=prefix + f"{factor}_url",
                          placeholder="https://...", label_visibility=hidden)


def _render_form(page, property_types):
    st.subheader("Your figures")
    title = page["title"]
    suggestion = page.get("suggested_type")
    if suggestion in property_types:
        st.caption(f"Wikipedia's page suggests this is a **{type_label(suggestion)}**. Change it if that is wrong.")

    # The type and the page-views tick sit OUTSIDE the form so that changing them refreshes
    # the starting age profile and audience figure straight away.
    type_key = f"wf_type|{title}"
    st.selectbox(
        "Property type", property_types, key=type_key, format_func=type_label,
        index=property_types.index(suggestion) if suggestion in property_types else None,
        placeholder="Choose a property type",
    )
    property_type = st.session_state.get(type_key)
    if property_type is None:
        st.caption("Choose a property type to continue.")
        return

    use_views = False
    if page.get("pageviews"):
        use_views = st.checkbox(
            "Use Wikipedia page views as the audience figure", value=True, key=f"wf_views|{title}",
            help="Page views measure online interest, not attendance. Untick this, or overwrite the figure below, "
                 "if you know the real attendance or TV audience.",
        )
    defaults = custom_property.default_values(page, property_types, use_views, chosen_type=property_type)

    prefix = f"wf|{title}|{property_type}|{use_views}|"
    st.session_state["wiki_form_prefix"], st.session_state["wiki_types"] = prefix, property_types

    with st.form("wiki_form"):
        st.text_input("Name", value=defaults["name"], key=prefix + "name")
        st.checkbox(
            "The audience includes children (under 18)", value=defaults["audience_includes_minors"], key=prefix + "minors",
            help="Turns on the youth rules: age-restricted brands are removed and the pitch talks about families.",
        )
        st.caption(
            "For each figure, enter a value if you have one (leave it blank if you do not), say whether it is "
            "**Sourced** or **Estimated**, and if sourced say where it came from. A blank figure is left out of the "
            "score and its weight is shared across the others."
        )
        for position, (factor, spec) in enumerate(custom_property.FIGURES.items()):
            _figure_row(prefix, factor, spec, defaults["figures"][factor], first=position == 0)

        st.markdown("**Engagement details** (optional, shown as context)")
        extra = st.columns(3)
        extra[0].number_input("Engagement rate (%)", min_value=0.0, max_value=100.0, value=None, step=0.1, key=prefix + "rate")
        extra[1].text_input("Instagram account", key=prefix + "account", placeholder="@name")
        extra[2].number_input("Followers", min_value=0, value=None, step=1, key=prefix + "followers")

        st.markdown("**Audience age profile** (percent in each age group; must total 100)")
        bands = st.columns(len(AGE_BANDS))
        for column, (part, label) in zip(bands, AGE_BANDS):
            column.number_input(label, min_value=0, max_value=100, value=int(defaults["age_profile"][part]), step=1, key=prefix + f"age_{part}")
        basis = st.columns([2, 6])
        basis[0].radio("Age profile is", ["Sourced", "Estimated"], index=1, horizontal=True, key=prefix + "age_mode")
        basis[1].text_input("Age profile source note", value="", key=prefix + "age_source",
                            placeholder="Starts as a default for this property type, which has not been researched")

        st.form_submit_button("Score this property", on_click=_score)

    for problem in st.session_state.get("wiki_form_errors", []):
        st.error(problem)
    scored = st.session_state.get("wiki_scored")
    if scored:
        st.success(f"Scored. '{scored}' is now in the ranking and selected in the sidebar. See the Analysis and Pitch below.")


# ---------------------------------------------------------------------------
# The whole section
# ---------------------------------------------------------------------------
def render(property_types):
    """Draw the lookup section. `property_types` are the types a property can have."""
    state = st.session_state
    has_work = bool(state.get("wiki_results") or state.get("custom_properties"))
    with st.expander("Look up a tournament or player on Wikipedia", expanded=has_work):
        st.caption(
            "Free: this uses Wikipedia's public APIs, with no key and no account. Type a name, pick the right page, "
            "then add or correct the figures Wikipedia does not have."
        )
        st.text_input("Tournament or player name", key="wiki_query", placeholder="For example: Queen's Club Championships, or Toby Samuel")
        st.button("Search Wikipedia", on_click=_search)

        if state.get("wiki_error"):
            st.error(state["wiki_error"])
        results = state.get("wiki_results")
        if results is not None and not results:
            st.warning("No Wikipedia pages matched that name. Try a different spelling or a fuller name.")
        if results:
            descriptions = {r["title"]: r["description"] for r in results}
            st.selectbox(
                "Which Wikipedia page?", list(descriptions), key="wiki_pick",
                format_func=lambda title: f"{title}: {descriptions[title] or 'no description'}",
            )
            st.button("Use this page", on_click=_use_page)

        page = state.get("wiki_page")
        if page:
            _render_page(page)
            if page["type"] != "disambiguation":
                _render_form(page, property_types)

        if state.get("custom_properties"):
            st.button("Remove my Wikipedia lookups", on_click=_remove_lookups)
