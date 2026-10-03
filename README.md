# Sponsorship Scout

A tennis sponsorship tool. Choose a tennis property (a tournament, a university team or a
player) and Sponsorship Scout will:

1. **Score** its commercial value out of 100, and show the breakdown, not just the total.
2. **Match** it with the best-fit brands from a brand list, and explain why each one fits.
3. **Draft a one-page partnership pitch**, written for the brand to read, that you can download.

You can also **look up any tournament or player on Wikipedia** (free, no key) and score that too.

> **What is real and what is not (version 2).**
> The five **properties are real**, with sourced or estimated figures collected on 2 October 2026.
> Every figure has a source and a confidence label (published, calculated or estimate), and the
> app shows them. The **brands are illustrative categories**, not real companies, and the **pitches
> are illustrative only**, not real proposals. The audience **age profiles** used in brand matching
> are still unresearched, judgement-based estimates.

Version 2 uses no web scraping and no paid services. The data lives in four CSV files that you
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
(age columns that do not total 100, a missing source, a category missing from another file, and so on).
`tests/test_data.py` also pins the exact researched figures, so when you refresh the data with new
research, update the `EXPECTED` table in `RealDataTests` to match.

---

## Using the app

- **Sidebar:** pick a property and move the five weight sliders. The weights are always
  rescaled to total 100, so the score stays out of 100. "Reset to defaults" puts them back.
- **Look up on Wikipedia:** type a tournament or player name, fetch its Wikipedia details, and score it
  (see "Looking up a property on Wikipedia" below).
- **Property ranking:** all properties ranked by score, with the chosen one tinted. It re-sorts
  live as you move the sliders. Properties from
  a Wikipedia lookup appear in the ranking too, marked "(Wikipedia lookup)".
- **Analysis:** the chosen property's score breakdown with a **confidence label next to each figure**,
  a collapsed "Data sources" panel, its top brand matches with reasons, and any brands removed by the
  youth-audience rule. This is the internal view.
- **Pitch:** choose a brand (it defaults to the top match, but you must choose if two brands tie
  for first), read the pitch, and download it as a Markdown file.

---

## Looking up a property on Wikipedia

You can score a tournament or player that is not in the data files, using Wikipedia's **free public
APIs** (no key, no account, no payment). Open "Look up a tournament or player on Wikipedia" near the top
of the app.

1. **Search.** Type a name and press "Search Wikipedia". The best few matching pages are listed with their
   one-line descriptions. Pick the right one and press "Use this page".
2. **See what Wikipedia says,** with a link to the source on every row:
   - the page **summary**;
   - **useful facts** from the page's info box (for a tournament: city, venue, surface, category, draw, prize
     money; for a player: ranking, plays, birthplace, career prize money, and so on);
   - **monthly page views** over the last 12 complete months, as a measure of public interest, with a chart.
3. **Check the form.** It starts with what Wikipedia gave us: the name, a suggested property type, and the page
   views as the audience figure. You add or correct the rest (engagements per post, higher-income share,
   broadcast tier, prestige, the audience age profile).
4. **Mark every figure Sourced or Estimated.** If you mark a figure *Sourced* you must say where it came from, or
   the form is rejected. An *Estimated* figure is hedged in the pitch ("about 3,000 people", "An estimated 40%...").
5. **Press "Score this property".** It is added to the property picker, the ranking, the analysis and the pitch,
   and scored by exactly the same scoring, matching and pitch code as the saved properties.

**Things to know**

- **Page views are not attendance.** They measure online interest. They fill the audience figure by default
  (the checkbox "Use Wikipedia page views as the audience figure" is ticked), they are labelled as a proxy, and
  the pitch describes them as "Wikipedia page views a year", never as "people" or "followers". Untick the box or
  overwrite the figure if you know the real attendance or audience.
- **Nothing is guessed for you.** Anything Wikipedia does not have starts blank. A blank figure is "not measured":
  it is left out of the score and its weight is shared across the other factors, as for Roehampton's engagement.
  The one starting value that is not from Wikipedia is the audience age profile, which starts as a default for the
  chosen property type and is labelled "not researched".
- **A lookup lives in your browser session only.** It is never written to the CSV files. Refreshing the page
  clears it; "Remove my Wikipedia lookups" clears it sooner. (To keep one, add it to `data/properties.csv`.)
- **Wikipedia coverage varies.** Small events and clubs often have no page, no info box or no page-view data.
  The app says what is missing and carries on. Only English Wikipedia is searched.
- **Attribution.** Wikipedia's text is shared under the CC BY-SA 4.0 licence; the app shows this with a link.
- **If the lookup says it cannot reach Wikipedia,** check your internet connection. If it mentions a
  *certificate*, Python on your Mac cannot verify secure websites: open the Python folder in Applications and run
  "Install Certificates.command", then try again.

**How it is built** (all in plain Python, nothing to install or pay for):
`wikipedia_lookup.py` talks to Wikipedia (search, summary, info box, page views) and is the only code that uses the
internet; `custom_property.py` checks the form and turns it into the same kind of record as a row of
`properties.csv`; `lookup_ui.py` is the section of the app you see. The tests replace Wikipedia with stand-ins, so
they never use the internet.

---

## The data files (in `data/`)

Open them in any spreadsheet or text editor. Lines starting with `#` at the top are notes and are
ignored by the app.

| File | One row per | What to edit |
|---|---|---|
| `properties.csv` | tennis property | the five figures, each with its source and confidence, plus the age profile |
| `brands.csv` | brand | category, target customer age profile, whether it is age-restricted |
| `category_fit.csv` | brand category | how well each category suits each property type (0 to 10) |
| `activations.csv` | activation idea | ideas shown in the pitch, written to the brand ("your name") |

### The figures in `properties.csv`

Each of the five figures has its own `_source`, `_source_url` and `_confidence` columns, and each row has a
`date_collected`. Leave `_source_url` blank if you have no link. Do not invent one.

| Figure | Column | How it is defined |
|---|---|---|
| Audience | `annual_audience_reach` | **Events:** attendance plus peak broadcast audience where published. Check `audience_source` for what each row counts (for example, Ilkley is attendance only because streaming is not published). **Players:** Instagram followers. |
| Engagement | `engagement_per_post` | **The scored figure.** Median of (likes + comments) over the 10 most recent **non-pinned** Instagram posts. Blank means "not measurable". |
| Engagement rate | `engagement_rate_pct` | The same median divided by followers. **Context only: it is shown but not scored** (see below). |
| Purchasing power | `high_income_share_pct` | % of the audience in higher-income brackets. All current values are estimates. |
| Broadcast | `broadcast_tier` | A 0 to 10 rating from the rubric below. |
| Prestige | `prestige_rating` | Your own 1 to 10 judgement. |

**Confidence labels** (every figure has one):

- **published**: taken straight from a published figure (for example, attendance from a tournament
  programme, or a follower count).
- **calculated**: worked out from published figures or posts (for example, a sum of attendance and a TV
  audience, or a median engagement rate).
- **estimate**: a judgement. Treat it with care.

**Why the median.** One viral post can have many times the normal likes and comments. A mean (average)
would be dragged up by it and overstate how engaged the following normally is. The median is the middle
value of the 10 posts, so one outlier cannot move it much. Pinned posts are skipped because they stay at
the top for weeks and collect more attention than a normal post.

**Why engagements per post, not the rate.** The score uses the number of engagements per post on a log scale,
not the engagement rate (engagements divided by followers). A rate **flatters small accounts**: a few hundred
loyal followers give a high percentage, while a big account with thousands of reactions per post looks
"weaker" because its rate is diluted across a huge following. Engagements per post counts how many real people
reacted. On the real data this matters: Toby Samuel has the highest rate (13.8%) but Queen's gets more than
twice as many engagements per post (2,025 against 878), and Queen's now scores higher on engagement. The rate
is still shown in the Analysis section as context. The scale runs from 10 engagements per post (0 out of 10)
to 10,000 (10 out of 10), on a log scale.

**When a figure cannot be measured.** If a figure is blank, it is left out of the score and its weight is
**shared across the factors that could be measured, in proportion to their weights**. The property is then
scored only on real evidence, and the total is still out of 100. For example, Roehampton has no dedicated
social account, so its engagement (weight 20) is left out and the other four weights scale up by 100/80
(audience 25 becomes 31.25, and so on). Nothing is made up: there is no "neutral" stand-in score. The
Analysis section shows this clearly: the factor is labelled "Not measured", both the weight you set and the
weight actually used are shown, and a notice explains what happened. There is no minimum account size: a
small account is not excluded, because scoring engagements per post on a log scale already treats it honestly
(a few reactions per post earn a low score).

### The broadcast rubric

`broadcast_tier` rates the coverage of the property's main matches. Free-to-air live TV is high, streaming
only is in the middle, and no coverage is low. The tier is used directly as the 0 to 10 score.

| Tier | Coverage | Example |
|---|---|---|
| 10 | Live free-to-air TV in several major markets | a Grand Slam |
| 9 | Live free-to-air TV, most or all days | Queen's, shown by the BBC |
| 7 to 8 | Live TV (free-to-air for part, or pay TV) plus full streaming | |
| 4 to 6 | Live streaming only: 6 for a large official platform, 4 for one court or a small audience | Toby Samuel (5), Lexus Ilkley Open (4) |
| 2 to 3 | Limited streaming or highlights | Roehampton junior event (2) |
| 1 | Social media video clips only | |
| 0 | No broadcast or streaming coverage | a university club's home matches |

The words in the right-hand column of the rubric (for example "live free-to-air television") are the
descriptions shown in the app and the pitch, and they live in `BROADCAST_RUBRIC` in `scoring.py`.
For a player, rate the coverage their typical matches get.

### Other things to know when editing

- The five age columns (`age_*_pct` and `target_age_*_pct`) must each total 100. The property age profiles
  have **not been researched**: they are judgement-based estimates (Queen Mary mostly 18 to 24, Roehampton a mix of
  under-18 players and parents aged 35 to 54, the rest carried over from version 1), labelled `estimate`, and brand
  matching depends on them.
- `audience_includes_minors` is `TRUE` for events with a youth audience. It switches on the youth rules below.
- `suitable_for_minors` (in `brands.csv`) is `FALSE` only for age-restricted products (alcohol, gambling and
  similar). Brands that merely do not target children stay `TRUE`.
- **To add a property:** add a row to `properties.csv` with all the columns. Its `property_type` must be a
  column in `category_fit.csv`.
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
| Audience size | 25 | log scale, 100 (0) to 10 million (10) |
| Social engagement | 20 | log scale on engagements per post, 10 (0) to 10,000 (10); left out and its weight shared if not measurable |
| Purchasing power | 20 | straight line, 0% (0) to 50% (10) of the audience in higher-income brackets |
| Broadcast exposure | 20 | the broadcast tier (0 to 10) from the rubric |
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
audience, engagement, category fit, purchasing power. The "highly engaged following" benefit needs **both** an
engagement rate of at least 4% (`ENGAGEMENT_MIN_PCT`) **and** at least 100 engagements per post
(`ENGAGEMENT_MIN_PER_POST`), because a high rate on its own can come from a very small account. The
"Social media engagement rate" line in the property stats follows exactly the same rule, so the two always
appear together or not at all. The sign-off name and title, and every threshold, are
named constants at the top of `pitch.py`. It starts with a short disclaimer line saying the brand is an
illustrative category and the pitch is not a real proposal.

---

## Key design decisions, and why

**The score**

- **A log scale for audience, with bounds set from the real data.** On a normal scale a 1.8 million audience
  would make a 20,000 audience look like nothing. On a log scale each tenfold jump adds the same number of
  points. The real audiences run from 150 (a university club) to 1.8 million (Queen's). The old floor of 1,000
  would have scored the 150 club at exactly 0, so the floor is now **100**. The ceiling is **10 million**: it
  keeps the real values well spread (about 0.4 to 8.5 out of 10) and leaves room above Queen's for the very
  biggest events.
- **Broadcast is a rated tier, not a count of impressions.** Impression counts are rarely published and are
  not comparable between a TV audience and a stream. A 0 to 10 tier with a written rubric is consistent and
  honest about being a judgement.
- **Engagements per post, not the engagement rate,** so small accounts are not flattered (see above).
- **Unmeasured factors are left out, not guessed.** Their weight is shared across the measured factors, so a
  property is scored only on real evidence. A made-up neutral score would have counted as evidence it is not.
- **Weights always total 100.** Sliders let you change what matters, but the weights are rescaled so the
  score never stops meaning "out of 100".
- **Prestige counts least.** It overlaps with audience and broadcast exposure, so weighting it heavily would
  reward the same thing twice.
- **Demographics means purchasing power only.** Age is left out of the score on purpose. A young or older
  audience is not worth less, it suits different brands, so age is handled in brand matching instead.
- **Premium and Challenger tournaments are separate property types.** Luxury brands fit a premium grass
  event far better than a Challenger, and local brands the other way round, so they need their own fit scores.
  Financial services fits a premium tournament at 9 because Queen's real title sponsor is a bank.
- **Category fit lives in a CSV, not in code,** so you can adjust it without touching Python.

**Honesty about the data**

- **Every figure carries a source and a confidence label,** and the app shows the label next to each figure.
  Estimates are never presented as published facts.
- **Source links are left blank rather than guessed.** Links are recorded for Ilkley (the tournament programme)
  and Roehampton (the ITF tournament page); Queen's is cited as "LTA, 2025" with no link yet.
- **The pitch never presents an estimate as a fact.** An estimated audience is written "about 3,000 people" and
  an estimated income share "An estimated 40% of the audience is in higher-income brackets". Claims about the
  audience's age mix are softened while the age profile is an estimate: "Your core customers, aged 35-54, are
  *likely* the tournament's largest audience group". Once an age profile is researched and its confidence label
  changed to published or calculated, the claim is stated plainly. The one exception is the families line for
  junior events ("The event reaches families: parents and young players together."), which describes the kind of
  event rather than the estimated age profile, so it is always stated plainly.
- **Age profiles are flagged as unresearched** in the data and in the app, because brand matching depends on them.
- **Players and events share one audience scale.** A player's audience is Instagram followers and an event's is
  attendance plus TV audience. They are different things, so comparing them directly is a simplification.

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
- **It shows only strengths.** For example the engagement rate appears only at 4% or above *and* with at least
  100 engagements per post (so a high rate on a tiny account is not shown), and the broadcast line only at
  tier 4 or above. It has no £ valuation or fee.
- **It is one separate function,** `generate_pitch`, so an AI writer can replace it later without changing
  anything else (see below).
- **"Placeholder" is hidden from displayed names** (app and pitch) but stays in the brand CSV and in the
  banners, so sample brands can never be mistaken for real companies.

**The Wikipedia lookup**

- **Only free, public, keyless services.** Wikipedia's search and summary, the Wikimedia page-views service, and
  the page's own info box. No account, no payment, no scraping of web pages (the info box is read from the
  page's official text through the API).
- **Every fetched figure shows its source link,** so you can check it.
- **Sourced figures must cite a source.** Without that rule, a guess could be marked "sourced" and look like fact.
- **Page views are offered as the audience figure, not forced on you,** because they measure interest rather than
  attendance. The pitch words them accordingly.
- **A lookup goes through the same scoring, matching and pitch as everything else,** so it can be compared fairly
  with the saved properties and gets the same honesty rules (confidence labels, "not measured", hedged wording).
- **It is not saved.** Writing user-typed figures into your data files automatically would be easy to get wrong.

**The build**

- **Plain Python, CSV files and no scraping or paid services,** so it runs anywhere and every number can be
  traced to a file you can open.
- **The tests never use the internet.** Wikipedia is replaced by stand-ins shaped like its real replies.
- **Tests use made-up data** wherever possible, so they keep passing when you edit the CSVs. A separate
  set of tests checks that the CSV files agree with each other, and one pins the researched figures.

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
| `data/` | the four editable CSV files |
| `wikipedia_lookup.py` | looks up a name on Wikipedia (the only code that uses the internet) |
| `custom_property.py` | turns the lookup form into a property record, with sourced/estimated checks |
| `lookup_ui.py` | the "Look up on Wikipedia" section of the app |
| `.streamlit/config.toml` | app settings (reload automatically when files are saved) |
| `requirements.txt` | the packages to install (Streamlit and watchdog) |
| `tests/` | automated tests (data, scoring, matching, pitch, display, app) |
| `show_scores.py`, `show_matches.py`, `show_pitch.py` | print results in the terminal, for checking |
| `PLAN.md` | what was agreed and why |

---

## Known limits of version 2

- Several figures are estimates (all the higher-income shares, the broadcast tiers, the prestige ratings, and
  the audiences of Roehampton and the university club). The confidence labels say which.
- Roehampton is scored on four factors, not five, because it has no social account to measure.
- A Wikipedia lookup is only as good as Wikipedia's page and the figures you add. Its page-view audience is a
  proxy for online interest, so it is not directly comparable with an attendance-plus-TV figure.
- The audience age profiles are unresearched judgements, so brand matching is only as good as those guesses.
  The pitch words its age-mix claims as "likely" for that reason.
- Brands are illustrative categories, so matches show which kind of brand fits, not which company.
- Matching considers age and category only. It does not consider geography, budget or existing sponsor conflicts
  (Queen's real title sponsor is a bank, so a bank "match" for Queen's would conflict in reality).
- The score is a relative comparison between the properties in the file, not a financial valuation.
- The pitch is a template. It reads well, but it is not tailored beyond the data fields.
