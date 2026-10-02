"""Prints the commercial score and breakdown for every property in properties.csv.

Run from the sponsorship_scout folder with:
    python3 show_scores.py
"""

from data_loader import load_properties
from scoring import DEFAULT_WEIGHTS, FACTOR_LABELS, rank_properties

print("PLACEHOLDER DATA: scores below use invented sample numbers.\n")
print("Weights:", ", ".join(f"{FACTOR_LABELS[f]} {w}" for f, w in DEFAULT_WEIGHTS.items()))
print("Each factor shows: score out of 10 -> points contributed\n")

for rank, (prop, result) in enumerate(rank_properties(load_properties()), start=1):
    print(f"{rank}. {prop['name']} ({prop['property_type']})  TOTAL: {result['total']:.1f} / 100")
    for factor, item in result["factors"].items():
        print(f"     {FACTOR_LABELS[factor]:<18} {item['score']:4.1f}/10 -> {item['points']:4.1f} of {item['weight']:.0f} points")
    print()
