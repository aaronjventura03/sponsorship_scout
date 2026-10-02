"""Checks the name-tidying helpers.

Run from the sponsorship_scout folder with:
    python3 -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import load_brands, load_properties
from display import clean_name, type_label


class CleanNameTests(unittest.TestCase):
    def test_removes_the_word_placeholder(self):
        self.assertEqual(clean_name("Placeholder Luxury Watchmaker"), "Luxury Watchmaker")
        self.assertEqual(clean_name("Placeholder Rising British Player (Top 150)"), "Rising British Player (Top 150)")

    def test_ignores_capital_letters_and_position(self):
        self.assertEqual(clean_name("PLACEHOLDER Sports Drink"), "Sports Drink")
        self.assertEqual(clean_name("Sports Drink (placeholder)"), "Sports Drink")

    def test_leaves_other_names_alone(self):
        self.assertEqual(clean_name("Luxury Watchmaker"), "Luxury Watchmaker")

    def test_does_not_touch_words_that_merely_contain_it(self):
        self.assertEqual(clean_name("Placeholders United"), "Placeholders United")

    def test_every_sample_name_is_cleaned(self):
        for row in load_properties() + load_brands():
            self.assertNotIn("placeholder", clean_name(row["name"]).lower(), row["name"])
            self.assertTrue(clean_name(row["name"]), row["name"])


class TypeLabelTests(unittest.TestCase):
    def test_capitalises_and_removes_underscores(self):
        self.assertEqual(type_label("premium_tournament"), "Premium tournament")
        self.assertEqual(type_label("player"), "Player")
        self.assertEqual(type_label("junior_event"), "Junior event")


if __name__ == "__main__":
    unittest.main()
