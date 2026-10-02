# Sponsorship Scout

A tennis sponsorship tool. Choose a tennis property (a tournament, a university team or a
player) and Sponsorship Scout will:

1. **Score** its commercial value out of 100, and show the breakdown, not just the total.
2. **Match** it with the best-fit brands from a brand list, and explain why each one fits.
3. **Draft a one-page partnership pitch**, written for the brand to read, that you can download.

> **All the data is placeholder data.** Every property, brand and number in this project is an
> invented example, not real research. The app shows a warning banner for as long as the data
> is marked as placeholder. Replace the CSV files with researched figures before relying on any result.

Version 1 uses no web scraping and no paid services. The data lives in four CSV files that you
can edit in Excel, Numbers or any text editor.

---

## Run it

You need Python 3 and the project's private environment (the `.venv` folder).

**Open the app** (from the `sponsorship_scout` folder):

```bash
.venv/bin/streamlit run app.py
```

It opens at http://localhost:8501. Press Ctrl+C in the terminal to stop it.

**Changed a file?** With the app running from the project folder, saving any project file reloads the
page automatically within a few seconds. This uses the `watchdog` package and the `runOnSave` setting in
`.streamlit/config.toml`. If the page ever looks out of date, stop the app (Ctrl+C), start it again and
refresh. (On a Mac, installing `watchdog` needs Apple's Command Line Tools: `xcode-select --install`.)

**If the `.venv` folder is missing**, create it once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Run the automated tests:**

```bash
.venv/bin/python -m unittest discover tests
```

All tests should say `OK`. Run them after editing any CSV file: they catch the easy mistakes
(age columns that do not total 100, a category missing from another file, and so on).

---

## Using the app

- **Sidebar:** pick a property and move the five weight sliders. The weights are always
  rescaled to total 100, so the score stays out of 100. "Reset to defaults" puts them back.
- **Property ranking:** all properties ranked by score, with the chosen one tinted. It re-sorts
  live as you move the sliders.
- **Analysis:** the chosen property's score breakdown, its top brand matches with reasons, and any
  brands removed by the youth-audience rule. This is the internal view.
- **Pitch:** choose a brand (it defaults to the top match, but you must choose if two brands tie
  for first), read the pitch, and download it as a Markdown file.

---

## The data files (in `data/`)

Open them in any spreadsheet or text editor. Lines starting with `#` at the top are notes and are
ignored by the app. Leave `is_placeholder` as `TRUE` until a row holds real, researched data.

| File | One row per | What to edit |
|---|---|---|
| `properties.csv` | tennis property | audience, engagement, income share, media reach, prestige, age profile |
| `brands.csv` | brand | category, target customer age profile, whether it is age-restricted |
| `category_fit.csv` | brand category | how well each category suits each property type (0 to 10) |
| `activations.csv` | activation idea | ideas shown in the pitch, written to the brand ("your name") |

**Things to know when editing**

- The five age columns (`age_*_pct` and `target_age_*_pct`) must each total 100.
- `annual_audience_reach` is the estimated unique people reached per year: in-person attendance,
  broadcast and streaming viewers, and digital or social reach, with each person counted once where possible.
- `audience_includes_minors` is `TRUE` for events with a youth audience. It switches on the youth
  rules described below.
- `suitable_for_minors` is `FALSE` only for age-restricted products (alcohol, gambling and similar).
  Brands that merely do not target children stay `TRUE`.
- **To add a property:** add a row to `properties.csv`. Its `property_type` must be a column in `category_fit.csv`.
- **To add a brand category:** add a row to `category_fit.csv` (with a friendly `category_label`) and at
  least two rows to `activations.csv`, then use the same category name in `brands.csv`.
- **To add a property type:** add a column to `category_fit.csv`, and a line to `PROPERTY_NOUN` in `pitch.py`.
  Optionally add a line to `CATEGORY_FIT_STYLE` too, to choose the wording (an event is a "natural home", a player
  a "natural ambassador", a team a "natural partner"). Types not listed there are worded like an event.
- `market` is stored in `properties.csv` and `brands.csv` so other markets can be added later.

---

## How it works

**Commercial score (`scoring.py`).** Five factors are each scored 0 to 10, then weighted to total 100.

| Factor | Default weight | How it is scored |
|---|---|---|
| Audience size | 25 | log scale, 1,000 (0) to 20 million (10) |
| Social engagement | 20 | straight line, 0% (0) to 8% (10) |
| Purchasing power | 20 | straight line, 0% (0) to 50% (10) of the audience in higher-income brackets |
| Media exposure | 20 | log scale, 100,000 (0) to 500 million (10) impressions |
| Prestige | 15 | your own 1 to 10 rating |

**Brand matching (`matching.py`).**

1. If the audience includes minors, age-restricted brands are removed first.
2. Each remaining brand scores 60% *audience overlap* (how closely the property's age profile matches the
   brand's target customers) plus 40% *category fit* (from `category_fit.csv`). The split is `MATCH_WEIGHTS`
   at the top of `matching.py`.
3. Ties are broken by higher audience overlap. Brands still exactly level share a joint rank (shown as `=3`),
   and all brands tied for the last top-3 place are shown.

**The pitch (`pitch.py`).** A fixed template with five sections: headline, the property, why the brand,
activation ideas and next steps. "Why the brand" holds up to three benefits, chosen in this priority order:
audience, engagement, category fit, purchasing power. The sign-off name and title, and every threshold, are
named constants at the top of `pitch.py`.

---

## Key design decisions, and why

**The score**

- **Log scales for audience and media.** On a normal scale a 12 million audience would make a 150,000
  audience look like nothing. On a log scale each tenfold jump adds the same number of points, so small
  properties still get meaningful scores next to big ones.
- **Weights always total 100.** Sliders let you change what matters, but the weights are rescaled so the
  score never stops meaning "out of 100".
- **Prestige counts least.** It overlaps with audience and media exposure, so weighting it heavily would
  reward the same thing twice.
- **Demographics means purchasing power only.** Age is left out of the score on purpose. A young or older
  audience is not worth less, it suits different brands, so age is handled in brand matching instead.
- **Premium and Challenger tournaments are separate property types.** Luxury brands fit a premium grass
  event far better than a Challenger, and local brands the other way round, so they need their own fit scores.
- **Category fit lives in a CSV, not in code,** so you can adjust it without touching Python.

**Matching and safety**

- **The youth rule is narrow.** Only age-restricted products (alcohol, gambling and similar) are removed
  for youth events. A private bank or watchmaker simply does not target children, and sponsors at junior
  events are often targeting parents.
- **Under-18s are never described as a brand's customers.** For youth events the pitch talks about
  families ("parents and young players together"). For all other events the customer benefit looks at adult
  age groups only.
- **The sample snack brand is a healthy snack brand.** UK rules restrict advertising food high in fat, sugar
  or salt to children.
- **Ties never depend on file order.** A tie on score is broken by audience overlap. If brands are still
  exactly level they share a joint rank, and you choose which one the pitch is written for.

**The pitch**

- **It is written for the brand, not for you.** It contains no scores, ratings or internal analysis. Those
  live in the app's separate Analysis section.
- **It shows only strengths.** For example the engagement rate appears only at 4% or above. It also has no
  £ valuation or fee.
- **It is one separate function,** `generate_pitch`, so an AI writer can replace it later without changing
  anything else (see below).
- **"Placeholder" is hidden from displayed names** (app and pitch) but stays in the CSV files and in the
  warning banners, so sample data can never be mistaken for real data.

**The build**

- **Plain Python, CSV files and no scraping or paid services,** so it runs anywhere and every number can be
  traced to a file you can open.
- **Tests use made-up data** wherever possible, so they keep passing when you edit the sample CSVs. A separate
  set of tests checks that the CSV files agree with each other.

---

## Adding AI-written pitches later

The pitch is made by one function, `generate_pitch(prop, match, activations)`, which returns Markdown text.
To use an AI writer, write another function that takes the same inputs and returns Markdown, then change the
single line in `app.py` that calls `generate_pitch`. Scoring, matching and the data files do not need to change.

---

## Project files

| File | Purpose |
|---|---|
| `app.py` | the Streamlit web app |
| `scoring.py`, `matching.py`, `pitch.py` | the three steps: score, match, pitch |
| `display.py` | tidies names for display (hides "Placeholder") |
| `data_loader.py` | reads the CSV files |
| `.streamlit/config.toml` | app settings (reload automatically when files are saved) |
| `requirements.txt` | the packages to install (Streamlit and watchdog) |
| `data/` | the four editable CSV files |
| `tests/` | automated tests (data, scoring, matching, pitch, display, app) |
| `show_scores.py`, `show_matches.py`, `show_pitch.py` | print results in the terminal, for checking |
| `PLAN.md` | what was agreed and why |

---

## Known limits of version 1

- All figures are invented placeholders. The score and matches are only as good as the data behind them.
- Matching considers age and category only. It does not consider geography, budget or existing sponsor conflicts.
- The score is a relative comparison between the properties in the file, not a financial valuation.
- The pitch is a template. It reads well, but it is not tailored beyond the data fields.
