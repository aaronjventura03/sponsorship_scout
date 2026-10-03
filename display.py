"""Small helpers that tidy names for display on screen and in the pitch.

The CSV files keep their full names (including the word "Placeholder", which
marks them as sample data). These helpers only change how a name is SHOWN.
"""

import re


def clean_name(name):
    """Hide the word "Placeholder" from a name.
    "Placeholder Luxury Watchmaker" is shown as "Luxury Watchmaker"."""
    without_word = re.sub(r"\bplaceholder\b", "", name, flags=re.IGNORECASE)
    without_empty_brackets = re.sub(r"\(\s*\)", "", without_word)  # "Name (placeholder)" would leave "()"
    return re.sub(r"\s+", " ", without_empty_brackets).strip()


def type_label(property_type):
    """Show a property type from the CSV as readable text.
    "premium_tournament" is shown as "Premium tournament"."""
    return property_type.replace("_", " ").capitalize()


def property_label(prop):
    """The name to show for a property. Properties made from a Wikipedia lookup are
    marked so they stand out from the saved ones: "Toby Samuel (Wikipedia lookup)"."""
    name = clean_name(prop["name"])
    return f"{name} (Wikipedia lookup)" if prop.get("from_wikipedia") else name
