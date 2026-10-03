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
- All sample data was PLACEHOLDER data in version 1. Version 2 (below) replaced the properties
  with real researched data; the brands are still illustrative placeholders.

## Version 2: real properties (data collected 2 October 2026)

The five placeholder properties were replaced with real ones. Brands stay illustrative category
placeholders, and pitches are illustrative only, not real proposals.

| id | Property | Type |
|---|---|---|
| P01 | Queen's (HSBC Championships) | premium_tournament |
| P02 | Lexus Ilkley Open | challenger_tournament |
| P03 | Lexus British Open Roehampton (ITF J300) | junior_event |
| P04 | Queen Mary Tennis Club (BUCS) | university_team |
| P05 | Toby Samuel (ATP ranking 100 on 2 October 2026) | player |

Model changes agreed for version 2:

- **Media impressions replaced by `broadcast_tier`**, a 0-10 rating with a written rubric (live
  free-to-air TV high, streaming only mid, none low). The tier is the factor's 0-10 score. The
  factor is now labelled "Broadcast exposure". Rubric documented in the README and in
  `BROADCAST_RUBRIC` in `scoring.py`.
- **Audience definition:** events = attendance plus peak broadcast audience where published (each
  row's `audience_source` says what it counts); players = Instagram followers.
- **Engagement is scored as engagements per post** (`engagement_per_post`): the median of (likes + comments)
  over the 10 most recent non-pinned posts, on a log scale from 10 (0/10) to 10,000 (10/10). Median because
  viral posts distort a mean. The engagement RATE (median divided by followers) is kept in the data and shown
  in the Analysis section as context only, because a rate flatters small accounts. Real medians: Queen's
  2,025, Toby Samuel 878, Ilkley 89, Queen Mary 23.
- **Unmeasurable factors are left out and their weight redistributed** proportionally across the measured
  factors (this replaced the earlier "neutral score of 5" rule). The property is scored only on real evidence
  and the total stays out of 100. Roehampton's engagement is the current example. (An earlier "account under
  1,000 followers is not measurable" rule was removed: engagements per post on a log scale already scores small
  accounts honestly.) The Analysis section labels the factor "Not measured", shows the weight set and the
  weight used, and explains it in a notice.
- **Audience log scale:** bounds changed from 1,000-20 million to 100-10 million, because the real data
  runs from 150 to 1.8 million and the old floor scored the 150-person club at exactly 0. New scores
  for the real audiences span about 0.4 to 8.5 out of 10.
- **New columns in `properties.csv`:** for each of the five figures a `_source`, `_source_url` and
  `_confidence` (published / calculated / estimate), plus `date_collected`, `engagement_account`,
  `engagement_followers`, and `age_profile_source` / `age_profile_confidence`. Source links are blank
  where none was recorded (none were invented).
- **category_fit:** financial_services for premium_tournament 8 to 9 (Queen's real title sponsor is a bank).
- **Display:** a new banner (real properties, illustrative brands, figures as of 2 October 2026); a
  confidence label next to each figure in the Analysis section; a collapsed "Data sources" panel; a
  note that the audience age profiles are estimates; the pitch's disclaimer now says the brand is an
  illustrative category and the pitch is not a real proposal.
- **Not researched:** the audience age profiles. They are judgement estimates, labelled `estimate`, and brand
  matching depends on them: Queen Mary mostly 18-24 (85%), Roehampton a mix of under-18 players and parents
  aged 35-54 (45% and 42%), the other three carried over from version 1. Researching them is the obvious next step.
- **Confidence labels chosen by Claude, not given in the brief:** broadcast tiers and prestige ratings are
  labelled `estimate` (a judgement against the rubric); the Queen's audience is `calculated` (a sum of
  two published figures); the Ilkley audience and the Toby Samuel follower count are `published`.

## Market

- UK first, values in GBP.
- `market` is a field in the property and brand CSVs, so European rows can be
  added later without changing code.

## Data files (all in `data/`)

| File | What it holds |
|---|---|
| `properties.csv` | The 5 real properties (version 2): each figure with its source, link and confidence |
| `brands.csv` | 13 placeholder brands, their category, target audience and whether they suit minors |
| `category_fit.csv` | Category fit, scored 0-10, for each brand category x property type (editable by you) |
| `activations.csv` | 2-3 activation ideas per brand category, used in the pitch |

Each file starts with `#` comment lines, and each row has an `is_placeholder` column
(`FALSE` for the real properties, `TRUE` for the illustrative brands). The app shows a banner
saying which parts are real and which are illustrative.

### Properties

See "Version 2" above. (Version 1 used five invented sample properties.)

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
| Engagement | 20 | Engagements per post on a log scale; left out (weight shared) if not measurable |
| Demographics | 20 | Purchasing power only: share of the audience in higher-income brackets |
| Broadcast exposure | 20 | The broadcast tier (0-10, from the rubric) |
| Prestige | 15 | Your own 1-10 rating in the CSV |

**What "audience" counts (version 2):** for events, attendance plus peak broadcast audience where
published (each row's `audience_source` says what it counts); for players, Instagram followers
(`annual_audience_reach` in `properties.csv`).

Scales (0 earns 0/10, the ceiling earns 10/10; set at the top of `scoring.py`):
audience 100 to 10,000,000 (log); engagements per post 10 to 10,000 (log); higher-income share
0% to 50% (straight line); broadcast tier and prestige are 0-10 ratings used as they stand.
A blank figure means the factor is not measured: it is left out and its weight is shared across the others.

- Prestige is weighted lower because it overlaps with audience and broadcast exposure.
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
| `wikipedia_lookup.py` | Looks up a name on Wikipedia (the only code that uses the internet) |
| `custom_property.py` | Turns the lookup form into a property record (sourced/estimated checks) |
| `lookup_ui.py` | The "Look up on Wikipedia" section of the app |
| `comparison.py` | The "compare like for like" mode (page views as every property's audience) |
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
   the app; the junior event excludes the age-restricted brand; 505 automated tests pass (after version 3.1)
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
19. Version 2: real researched properties, a broadcast tier instead of media impressions, median
    engagement with a neutral score when it cannot be trusted, per-figure sources and confidence
    labels, a new banner, and category-fit financial_services for premium_tournament 8 to 9. See
    "Version 2" near the top of this file.

20. Version 2 review changes: engagement scored per post on a log scale (rate shown as context);
    unmeasurable factors have their weight redistributed instead of getting a neutral score; the pitch
    prefixes estimated figures with "about" or "An estimated"; age profiles adjusted by judgement for
    Queen Mary and Roehampton (still flagged as estimates); the Ilkley description updated; source links
    added for Ilkley and Roehampton (Queen's stays "LTA, 2025" with no link).

21. Final changes: the "account under 1,000 followers" rule was removed (engagements per post on a log
    scale already scores small accounts honestly), and the pitch now softens audience-age claims
    ("are likely the tournament's largest audience group", "is likely to reach families") wherever a
    property's age profile is an estimate. Published or calculated profiles are stated plainly. All five
    properties currently have estimated profiles, so every pitch is hedged.

22. Two small pitch changes: the families bullet for junior events is always stated plainly (it describes
    the kind of event, not the estimated age profile), and the "highly engaged following" bullet now needs
    both an engagement rate of at least `ENGAGEMENT_MIN_PCT` (4%) and at least `ENGAGEMENT_MIN_PER_POST`
    (100) engagements per post. Of the current five properties only Toby Samuel gets the bullet.

23. The engagement rate line in the property stats now follows the same two-part rule as the "highly
    engaged" bullet (rate at least 4% and at least 100 engagements per post), so a small account with a high
    rate no longer shows a flattering percentage. The line and the bullet always appear together.

## Version 3: Wikipedia lookup and a property-type filter

Goal: score a tournament or player that is not in the data files, using only free public APIs (no key,
no account, no payment), and rank one property type at a time.

What was built:

- **`wikipedia_lookup.py`** (the only code that uses the internet): Wikipedia search, page summary, page
  views from the Wikimedia service (last 12 complete months, average and a year's worth), and facts read
  from the page's info box (wikitext cleaned of links, references and templates). Every fetched item
  carries a source link. Errors become plain-English messages; the facts and page views are best-effort,
  and the summary is required. Uses the `certifi` certificate list because python.org Python on a Mac
  often cannot verify secure sites (found and fixed while testing against the live service).
- **`custom_property.py`**: turns the form into a record with the same columns as `properties.csv`. Each
  figure is marked Sourced or Estimated; a Sourced figure must cite a source; a blank figure is "not
  measured" (its weight is redistributed). Page views fill the audience figure by default (labelled
  "calculated", and a proxy for public interest, not attendance). The age profile starts as a default for
  the chosen type, labelled "not researched". Nothing else is guessed.
- **`lookup_ui.py`**: the app section (search, pick a page, "What Wikipedia gave us" table with source links,
  a page-view chart, the form, validation). Wikipedia is contacted only inside button callbacks, never on a
  plain re-run. A lookup is kept in the browser session only and is never written to the CSV files.
- **App**: a lookup joins the property picker, the ranking (marked "(Wikipedia lookup)"), the analysis and the
  pitch. New "Rank one property type at a time" filter above the ranking table (ranks count within the type).
- **Pitch**: copes with blank figures; an audience that is Wikipedia page views is described as "Online
  interest: N Wikipedia page views a year", never as people or followers.
- **Tests**: grew from 250 to 434. None uses the internet: `tests/wiki_fixtures.py` holds stand-in Wikipedia
  replies shaped like the real ones, and a guard fails any test that reaches for the real downloader.

Decisions: page views are offered as the audience figure (ticked by default, easy to untick) because they
measure interest, not attendance. Lookups are not saved automatically. Only English Wikipedia is searched.

## Version 3.1: comparing like for like

Problem: a Wikipedia lookup's audience (page views) is not comparable with the saved properties' audience
(attendance + TV, followers, guesses).

Options considered: (A) score every property's audience from page views; (B) leave page views out of the
score; (C) convert page views to "audience equivalents" with an exchange rate; (D) make A an optional switch.
C was rejected (the saved properties give contradictory rates: about 12 for Queen's, about 0.05 for Toby Samuel).
D was built.

What was built:

- A **"Compare like for like"** switch above the ranking table (off by default). When on, every property's
  audience is its Wikipedia page views over the same last 12 complete months, so a lookup ranks fairly against
  the saved properties. `comparison.py` fetches the page views (once per session, cached) and returns COPIES of the
  properties with the audience swapped; the scoring, ranking, analysis and type filter then run unchanged.
- A new **`wikipedia_title`** column in `properties.csv`: Queen's Club Championships, Ilkley Trophy (the Lexus
  Ilkley Open's page; "Ilkley Open" is a different, historic event), Toby Samuel; blank for Roehampton and
  Queen Mary, which have no Wikipedia page (checked 3 October 2026).
- A property with no page has a blank audience in this mode: "not measured", its weight shared across its other
  factors. A failed download is reported and the standard scores are shown (never confused with "no page").
- The analysis shows the page views next to the standard figure; a table lists every property's page views, with
  source links. A nudge appears when a lookup with a page-view audience is ranked in standard mode.
- The **pitch ignores the switch** and keeps each property's own best figures.
- Tests: 434 grew to 505, none using the internet. A deliberate break of the feature made 10 of them fail.

On the live figures (3 October 2026) the switch gives: Queen's 76.9 (was 82.2), Toby Samuel 57.8 (51.5),
Roehampton 47.3 (41.7), Ilkley 46.5 (49.3), Queen Mary 12.5 (10.3). Roehampton overtakes Ilkley because it is
scored on only three factors (audience and engagement are both unmeasured), which shows the limit of the
"share the weight" rule.

## Open items

- None at the moment. (Agreed in step 6: the user chooses the brand when there is a joint first.
  Done.)
