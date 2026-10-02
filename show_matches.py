"""Prints the top brand matches for every property in properties.csv.

Run from the sponsorship_scout folder with:
    python3 show_matches.py
"""

from data_loader import load_brands, load_category_fit, load_properties
from matching import MATCH_WEIGHTS, match_brands

brands = load_brands()
category_fit = load_category_fit()

print("Properties are real; brands are illustrative categories; audience age profiles are unresearched estimates.\n")
print(f"Match split: {MATCH_WEIGHTS['audience_overlap']} audience overlap / {MATCH_WEIGHTS['category_fit']} category fit\n")

for prop in load_properties():
    result = match_brands(prop, brands, category_fit)
    print(f"=== {prop['name']} ({prop['property_type']}) ===")

    for match in result["matches"]:
        print(f"  {match['rank_label']}. {match['brand']['name']}  MATCH: {match['total']:.1f} / 100")
        print(f"     (overlap {match['overlap_points']:.1f} points + category fit {match['fit_points']:.1f} points)")
        for reason in match["reasons"]:
            print(f"     - {reason}")

    if result["excluded"]:
        names = ", ".join(item["brand"]["name"] for item in result["excluded"])
        print(f"  Removed by the youth-audience rule: {names}")
    print()
