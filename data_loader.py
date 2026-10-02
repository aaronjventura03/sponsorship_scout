"""Reads the CSV files in the data/ folder.

Each file can start with lines beginning with '#'. These are notes for you
(for example the "PLACEHOLDER DATA" warning) and are skipped when reading.

Numbers are turned into numbers, and TRUE/FALSE into True/False, so the rest
of the code does not have to worry about it.
"""

import csv
import os
from pathlib import Path

# The data/ folder sits next to this file.
DEFAULT_DATA_DIR = Path(__file__).parent / "data"


def data_dir():
    """The folder the CSV files are read from. Normally the data/ folder.
    Setting the SCOUT_DATA_DIR environment variable points it somewhere else,
    which is only used by the tests, so they can try out made-up data."""
    return Path(os.environ.get("SCOUT_DATA_DIR", DEFAULT_DATA_DIR))


def _convert(text):
    """Turn a CSV cell (always text) into a bool, int, float or plain text."""
    text = text.strip()
    if text.upper() == "TRUE":
        return True
    if text.upper() == "FALSE":
        return False
    for number_type in (int, float):
        try:
            return number_type(text)
        except ValueError:
            pass
    return text


def read_csv(filename):
    """Read one CSV file from the data folder. Returns a list of rows,
    where each row is a dictionary like {"name": "...", "prestige_rating": 9}."""
    with open(data_dir() / filename, newline="", encoding="utf-8") as file:
        lines = [line for line in file if not line.startswith("#")]
    return [
        {column: _convert(value) for column, value in row.items()}
        for row in csv.DictReader(lines)
    ]


def load_properties():
    return read_csv("properties.csv")


def load_brands():
    return read_csv("brands.csv")


def load_category_fit():
    return read_csv("category_fit.csv")


def load_activations():
    return read_csv("activations.csv")
