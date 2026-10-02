# Sponsorship Scout: Project Plan

A portfolio tool for tennis sponsorship. You choose a tennis property, the tool
scores its commercial value out of 100, matches it with the 3 best-fit brands,
and drafts a one-page partnership pitch for the top match.

This file records what we have agreed. Update it whenever a decision changes.

## Version 1 constraints

- Python with a simple Streamlit web interface.
- Data lives in CSV files you can edit yourself (see "Data files" below).
- No web scraping and no paid APIs.
- Pitch writing sits in its own function so AI-written pitches can replace it later.
- All sample data is PLACEHOLDER data. Names are descriptive, not real.

## Market

- UK first, values in GBP.
- `market` is a field in the property and brand CSVs, so European rows can be
  added later without changing code.

## Data files (all in `data/`)

| File | What it holds |
|---|---|
| `properties.csv` | The 5 sample properties and their raw numbers |
| `brands.csv` | 13 placeholder brands, their category, target audience and whether they suit minors |
| `category_fit.csv` | Category fit, scored 0-10, for each brand category x property type (editable by you) |
| `activations.csv` | 2-3 activation ideas per brand category, used in the pitch |

Each file starts with a `#` comment line saying it is placeholder data, and each
row has an `is_placeholder` column (where relevant). The app will also show a
visible placeholder banner.

### Sample properties

1. Premium ATP 500-level grass tournament, London
2. ATP Challenger event, UK
3. Rising British player, ranked around the top 150
4. BUCS university tennis team
5. ITF junior tournament (family and youth audience)

### Property types (used by `category_fit.csv`)

`premium_tournament`, `challenger_tournament`, `player`, `university_team`, `junior_event`

### Brand categories (13 brands across 12 categories)

luxury_watches, luxury_jewellery, financial_services, student_services,
sportswear, sports_equipment, healthy_snacks, food_drink, premium_drinks,
automotive, tech, local_business (a regional car dealership, suitable for minors).
Each category has a friendly `category_label` in `category_fit.csv`, used in explanations.

## Commercial score (out of 100)

Five factors, each scored 0-10 on a defined scale, then weighted.

| Factor | Default weight | How it is scored |
|---|---|---|
| Audience size | 25 | Log scale, so small and large properties both get meaningful scores |
| Engagement | 20 | Engagement rate mapped linearly to 0-10 |
| Demographics | 20 | Purchasing power only: share of the audience in higher-income brackets |
| Media exposure | 20 | Annual media impressions, log scale |
| Prestige | 15 | Your own 1-10 rating in the CSV |

**What "audience" counts:** the estimated unique people reached per year, as a mix of
in-person attendance, broadcast and streaming viewers, and digital or social reach, with
each person counted once where possible (`annual_audience_reach` in `properties.csv`).

Scales (0 earns 0/10, the ceiling earns 10/10; set at the top of `scoring.py`):
audience 1,000 to 20,000,000 (log); media impressions 100,000 to 500,000,000 (log);
engagement 0% to 8% (straight line); higher-income share 0% to 50% (straight line);
prestige is your 1-10 rating as it stands.

- Prestige is weighted lower because it overlaps with audience and media exposure.
- Demographics does NOT include age. Age fit is handled in brand matching via
  audience overlap, so young or older audiences are not penalised in the score.
- The interface has sliders for the weights, starting at the defaults above.
  The app rescales the weights so they always total 100, and shows the effective weights.

## Brand matching

- Hard rule first: if the property's audience includes minors, brands marked
  `suitable_for_minors = FALSE` are removed before any scoring. That flag means
  age-restricted products only (alcohol, gambling and similar). Brands that merely do not
  target children (private bank, watchmaker and so on) stay in, because sponsors at junior
  events are often targeting parents.
- Tiebreaker: if two brands have the same match score, higher audience overlap ranks first.
  If they are still exactly level, they share a joint rank shown as "=3" (next rank skipped:
  1, 2, =3, =3, 5), and all brands tied for the last top-3 place are shown, so a property can
  show more than 3 brands. File order never decides.
- Each remaining brand gets a fit score from two parts. The agreed split is
  60% audience overlap and 40% category fit. It is set in `MATCH_WEIGHTS` at the top of
  `matching.py` (as is `TOP_N`, the number of brands returned).
  - **Audience overlap:** how closely the property's age profile matches the
    brand's target age profile (both stored as shares across 5 age bands).
  - **Category fit:** read from `category_fit.csv` (brand category x property type, 0-10).
- Top 3 brands are shown, each with a plain-English reason.

## Pitch (version 1)

A fixed template filled with data, not AI. Shown on screen as a formatted page,
with a button to download it as a Markdown file. **The pitch is written for the brand to
read.** It contains no scores, ratings, factor tables or match scores. Those go in a
separate analysis panel in the app (step 6). Five sections:

1. Headline: "Partnership opportunity: [Property] x [Brand]"
2. The property: description and four key stats. Large numbers are written in words
   ("12 million", "250 million").
3. Why [brand]: 2-3 benefits to the brand in plain English (for example "Your core
   customers, aged 35-54, are the tournament's largest audience group"), built from the
   data. Candidates in priority order, first three kept: audience, engagement ("A highly
   engaged following, well above typical engagement rates", only at or above
   `ENGAGEMENT_MIN_PCT`), category fit, purchasing power. A reach bullet is added if fewer
   than 2 apply. No "UK link" line.
   - For properties with `audience_includes_minors = TRUE` the audience bullet is about
     families ("The event reaches families: parents and young players together."). Under-18s
     are never described as the brand's customers, and the brand is never said to get "access
     to" them. For all other properties the customer bullet looks at adult age groups only.
4. Activation ideas: 2-3 ideas from `activations.csv`
5. Next steps: a concrete ask for a 30-minute call to walk through the partnership
   options, referring back to the activation ideas.

The word "Placeholder" is hidden from every name shown in the app and the pitch (it stays in
the CSVs, and the app's placeholder banner stays). The pitch ends with a sign-off, "Prepared by
Aaron Ventura, Partnerships", whose name and title are constants at the top of `pitch.py`
(`SIGNOFF_NAME`, `SIGNOFF_TITLE`). On screen the pitch headings are shown smaller so it reads
like a document; the downloaded Markdown keeps the original headings.

No GBP valuation or fee in the pitch. The pitch lives in its own function
(`generate_pitch(prop, match, activations)`) so AI can replace it later.

## Analysis panel (step 6)

The internal numbers (commercial score and factor breakdown, match scores, ranks, matching
reasons, brands removed by the youth rule) are shown in a separate panel in the app, not
in the pitch.

When brands share the top rank (a joint first, shown as "=1"), the app lets you choose
which brand the pitch is written for.

## Project files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit web app |
| `scoring.py` | Commercial score (weights, scales, ranking, rank labels) |
| `matching.py` | Brand matching (overlap, category fit, youth rule, ranks, reasons) |
| `pitch.py` | The brand-facing pitch template (sign-off constants at the top) |
| `display.py` | Hides "Placeholder" from displayed names, formats property types |
| `data_loader.py` | Reads the CSV files |
| `data/` | The four editable CSV files |
| `tests/` | Automated tests (data, scoring, matching, pitch, display, app) |
| `show_scores.py`, `show_matches.py`, `show_pitch.py` | Command-line printouts for checking results |
| `README.md` | How to run, edit and extend the project |

## Build steps

1. Set-up: PLAN.md, folder structure, requirements file. (done)
2. Data: the four CSV files. (done, reviewed) **Review pause: you check the data.**
3. Scoring: the code and tests that produce the 0-100 score and breakdown. (done, reviewed)
   **Review pause: you check the five property scores and their ranking before matching is built.**
4. Matching: overlap, category fit, minors rule, explanations, tests. (done, reviewed)
   **Review pause: you check the matching logic and results.**
5. Pitch: the standalone pitch function. (done: `pitch.py`, `show_pitch.py`, tests)
6. Interface: the Streamlit app (`app.py`). (done, reviewed) **Review pause: you check the app.**
   Layout: sidebar (property picker, weight sliders, reset); top ranking table of all
   properties that updates live; Analysis (score breakdown, top brand matches with reasons
   and scores, brands removed by the youth rule); Pitch (brand picker defaulting to #1 and
   required when there is a joint first, rendered pitch, Markdown download); placeholder
   banner always visible. Streamlit is installed in a private `.venv` folder inside the project.
   Run it with: `.venv/bin/streamlit run app.py` (from the `sponsorship_scout` folder).
7. Final review: (done) all 5 properties run end to end through scoring, matching, pitch and
   the app; the junior event excludes the age-restricted brand; 133 automated tests pass
   (23 of them drive the app and need Streamlit); README written.

## Changes agreed after the first plan

1. Demographics is purchasing power only (no age component).
2. Added a review pause after step 3.
3. Category fit is stored in an editable CSV, not in code.
4. The `tournament` type was split into `premium_tournament` and `challenger_tournament`,
   each with its own category-fit scores (luxury fits premium far better; local and
   regional brands fit a Challenger better).
5. Added a `local_business` brand and category (B13). Fit scores: premium 2, challenger 9,
   player 3, university 6, junior 7. Sports equipment for player raised 9 to 10;
   automotive for junior_event raised 1 to 3.
6. Scoring uses only Python's built-in tools (csv, unittest), so nothing needs installing
   until the Streamlit interface in step 6.

7. `suitable_for_minors` redefined as age-restricted products only. Only the sparkling
   wine is now flagged FALSE.
8. P05 (junior) higher-income share raised 28% to 40%. P02 (Challenger) audience lowered
   600,000 to 150,000.
9. The kids snack brand became a healthy snack brand (category `food_drink_youth` renamed
   `healthy_snacks`), because UK rules restrict advertising high fat, sugar or salt food to children.
10. Tiebreaker added (higher audience overlap wins) and a `category_label` column added to
    `category_fit.csv`.

11. Category fit tweaks: automotive for premium_tournament 10 to 9 (watches are the signature
    tennis sponsor category); financial_services for junior_event 3 to 6 (affluent parents).

12. Pitch tweaks: the engagement rate is shown only if it is at least 4% (`ENGAGEMENT_MIN_PCT`
    in `pitch.py`), the higher-income figure is removed from the stats (it stays in the
    benefit bullet), and activation ideas in `activations.csv` are written in the second person.

13. Step 7 review fixes: "Placeholder" hidden from displayed names; ranking table shows only
    Rank, Property, Type and Score; property types capitalised ("Premium tournament"); smaller
    on-screen headings (the Analysis heading is now short, with the property name on the line
    below); the matches caption reads "Match score combines audience overlap (60%) and category
    fit (40%). Brands marked '=' are tied."; category-fit reasons no longer repeat the number
    ("Category fit 9/10: premium drinks brands suit a premium tournament well."); sign-off added
    to the pitch.

14. The ranking table has no "Chosen" column; the chosen property's row is tinted instead.
    In the factor breakdown table the "Your figure" column is now called "Figure".

15. Final step 7 fixes: families wording for youth events and a test that no pitch (all brands,
    all properties) calls under-18s customers; an engagement benefit bullet (max 3 bullets,
    priority audience, engagement, category fit, purchasing power); heading link icons hidden
    across the whole page (not only in the pitch); README rewritten with the key design
    decisions and why.

16. Category-fit wording by property type: events are "a natural home", a player is "a natural
    ambassador" (named, e.g. "Rising British Player (Top 150) is a natural ambassador for sports
    equipment brands like yours"), a university team is "a natural partner". Set in
    `CATEGORY_FIT_STYLE` and `CATEGORY_FIT_WORDING` in `pitch.py`.
17. Apple's Command Line Tools installed. `watchdog` installed and listed in `requirements.txt`;
    `.streamlit/config.toml` sets `runOnSave = true`, so saving a file reloads the open page
    automatically (tested: an edit to `pitch.py` appeared in the open page within 5 seconds).
18. Git set up (branch `main`) with a first commit.

## Open items

- None at the moment. (Agreed in step 6: the user chooses the brand when there is a joint first.
  Done.)
