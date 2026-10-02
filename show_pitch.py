"""Prints the partnership pitch for a property's top brand match.

Run from the sponsorship_scout folder with:
    python3 show_pitch.py          (uses the first property, P01)
    python3 show_pitch.py P03      (uses the property with that id)
"""

import sys

from data_loader import load_activations, load_brands, load_category_fit, load_properties
from matching import match_brands
from pitch import generate_pitch

properties = load_properties()
wanted_id = sys.argv[1] if len(sys.argv) > 1 else properties[0]["id"]
prop = next((p for p in properties if p["id"] == wanted_id), None)
if prop is None:
    sys.exit(f"No property with id '{wanted_id}'. Choose from: {', '.join(p['id'] for p in properties)}")

# If brands share the top rank, this uses the first of them. (The app will let you choose.)
top_match = match_brands(prop, load_brands(), load_category_fit())["matches"][0]
print(generate_pitch(prop, top_match, load_activations()))
