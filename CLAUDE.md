# CLAUDE.md: Stack Overflow Decline project

Project plan: [04-stackoverflow-decline.md](04-stackoverflow-decline.md). Data provenance: [DATA.md](DATA.md).

## How we work

1. The project is built by running the numbered prompts below **one at a time, in order**. The user starts each one by saying "Run P05" (or similar).
2. Act as an expert data scientist: think about identification, measurement error and alternative explanations, not just code.
3. Run only the prompt asked for. If a prompt turns up something that changes later prompts, say so in the findings and propose an edit to this file. Don't edit the prompt list unless asked.
4. **After each prompt, stop and report findings** in this format:
   - **Done:** what was built or run (files with links)
   - **Key results:** the numbers that matter, with units and dates
   - **Figures:** paths to any charts made, with one line on what each shows
   - **Data issues / surprises:** anything odd, and how it was handled
   - **Decisions for you:** choices that need the user's input (keep it to 0–3)
   - **Next:** the next prompt ID and anything to check before running it
5. When a prompt is finished and its findings are approved, tick its box in the list below and add a one-line result next to it. When every prompt in a phase is ticked, add "✅ DONE" to the phase heading.
6. Pre-registration (P03) is locked before any model is fitted on post-2022 data. Later changes go in a dated "Deviations" section of `PREREGISTRATION.md`, never as silent edits.

## Project facts

- **Raw data (read-only):** `/Volumes/Drive3/data/<site>/` holds the 2026-Q3 dump: 27 sites, 8 XML tables each, cut-off 2026-09-30. The external drive must be mounted.
- **Processed data:** `/Volumes/Drive3/sod/` (Parquet, DuckDB). Paths come from env vars `SOD_RAW_DIR` and `SOD_DATA_DIR`. Never hard-code them.
- **Never commit data.** Only small reference CSVs in `data/reference/` go in git.
- **Stack:** Python with `uv`, `lxml.iterparse`, PyArrow/Parquet, DuckDB, statsmodels, pysyncon, PyMC or bambi, matplotlib, Quarto.
- **Big files:** Stack Overflow `PostHistory.xml` is 185 GB and `Posts.xml` is 106 GB. Stream them, never load them whole. Write Parquet in row-group batches. Drop `Body` and `Text` after computing features.
- **Licence:** CC BY-SA 4.0. Publish derived metrics only, never post text or user names.
- **Dates:** all timestamps are UTC. Weeks run Monday to Sunday. The ChatGPT break is week of 2022-11-28 (release 2022-11-30).
- **Site groups:** treatment = stackoverflow.com. SO in other languages = ru, es, pt, ja. Tech sites also exposed to AI = superuser, serverfault, askubuntu, unix, softwareengineering, dba. Comparison pool = math (caution), physics, chemistry, biology, english, philosophy, history, cooking, diy, travel, bicycles, gaming, scifi, movies, rpg. Context = meta.stackoverflow.

## Prompt list

### Phase 0: Setup and guardrails ✅ DONE

- [x] **P00: Repo scaffold.** *Done 2026-10-19: Python 3.12 + uv, all deps import, 4 tests pass, check-env OK; private repo johnpospisil/stackoverflow-decline.* Set up the project: `git init`, `pyproject.toml` with `uv` and pinned dependencies, `Makefile` with targets `ingest build models figures report all test`, the `src/sod/` package layout from the plan, `tests/`, `notebooks/`, `report/`, `app/`, a `.gitignore` that excludes data, and `src/sod/config.py` reading `SOD_RAW_DIR` and `SOD_DATA_DIR`. Add a `make check-env` target that confirms the drive is mounted and reports free space. Create a **private** GitHub repo with `gh` and push to it; it becomes public at launch (P33/P34). **Findings:** environment versions, disk space, and anything that failed to install.

- [x] **P01: Dump integrity and watermarking.** *Done 2026-10-19: 27/27 SHA-256 match the community list (no official list yet); no watermarks in the 26 smaller sites; XML rows are unordered.* Compute SHA-256 hashes of the original `.7z` files (or the extracted XML if the archives are gone). Compare them against the official checksum answer on Meta and the community-maintained hash mirror. Check whether the 2026-Q3 dump is on the community list of watermarked or poisoned dumps, and research what the watermarking changes (text, dates, IDs, counts?). **Findings:** match or no match for each site, watermark status, which of our measures could be affected, and the result written into DATA.md.

- [x] **P02: Event timeline.** *Done 2026-10-19: 35 sourced events; main break ChatGPT 2022-11-30; exclusion windows COVID (2020-03-11 to 06-30) and moderator strike; Italy block not used.* Build `data/reference/events.csv` (date, event, category, source URL) covering: ChatGPT, GPT-4, Copilot GA, Copilot Chat, Claude and Gemini releases, SO's AI-answer ban, the moderator strike start and end, the OpenAI–SO partnership, SO layoffs, major SO UI or policy changes (e.g. question wizard, staging ground), and dump or SEDE outages. Every row needs a primary source. **Findings:** the table, with any dates that are disputed.

- [x] **P03: Pre-registration.** *Done 2026-10-20: locked at tag `prereg-v1`; primary = monthly synthetic control vs 15 donors, 2017-01 to 2022-11 pre-period, smallest effect of interest −10%.* Write `PREREGISTRATION.md` before any model is fitted: the primary estimand (log weekly SO questions vs counterfactual, average over 2023-01 to 2026-09), the primary model and comparison group, secondary hypotheses (tag age, question mix, newcomers, answerers), what result would count as a null or would refute the hypothesis, the multiple-comparison approach for tags, and the planned robustness checks. **Findings:** a one-paragraph summary of what we committed to, plus open judgement calls for the user to decide.

### Phase 1: Ingest (XML → Parquet) ✅ DONE

- [x] **P04: Parser tests first.** *Done 2026-10-20: 61 tests pass (45 fixture, 16 real-file); no unknown columns; SO Posts parse at ~31k rows/s with 28 MB memory; SO uses `<a><b>` tag format.* Create small fixture XML files (about 20 rows per table, including missing attributes, unicode, HTML in Body, `&#xD;` entities and multi-tag strings). Write failing pytest tests for a streaming row parser and for Body feature extraction (length, number of `<pre><code>` blocks, has-code, number of links). Then implement until they pass. **Findings:** test count, edge cases found in the real files.

- [x] **P05: Posts ingest.** *Done 2026-10-20: 73.1M posts (SO 24.1M questions, 36.1M answers) → 2.8 GB Parquet in 45 min; cut-off 2026-09-30 confirmed; full watermark scan clean; closed questions under-represented (deleted posts missing).* Stream `Posts.xml` for all 27 sites into partitioned Parquet (`site=`, `year=`). Keep the IDs, type, parent and accepted-answer IDs, dates, score, views, owner ID, tags as a list, answer and comment counts, closed date, plus the Body/Title features; drop raw text. Log rows per second and peak memory, and allow a run to resume after an interruption. Run the small sites first, then SO. **Watermark guard:** during the full SO scan, count rows matching the known v1 watermark (ID ≥ 1,000,000,000, or a question/answer owned by user -1 with no PostHistory) and fail if any are found unless they are filtered out and logged. Record the SO result in DATA.md. Rows are not in ID or date order, so compute max/min over all rows. **Findings:** rows by site and post type, run time, Parquet size, null rates per column, the min/max dates for each site (confirms the 2026-09-30 cut-off), and the watermark-scan result.

- [x] **P06: Users, Votes, Comments, PostLinks, Tags ingest.** *Done 2026-10-20: 478M rows → 4.3 GB Parquet in 21 min; votes have no voter (0.12%) and no time of day; close votes only in PostHistory after 2013-06.* Users: ID, creation date, reputation, last access, location present (yes/no). Votes: post ID, vote type, date (Votes has no user ID for most types; confirm). Comments: post ID, date, user ID, text length. PostLinks: type 3 = duplicate. Tags: name, count, excerpt/wiki IDs. **Findings:** row counts, sizes, and which vote types are present.

- [x] **P07: PostHistory ingest (filtered).** *Done 2026-10-20: 74M events kept (0.93 GB) in 41 min; SO 1.195M closures (60% duplicate); deleted posts' history absent; tag analyses use tags at time of asking (prereg clarification).* Stream SO's 185 GB `PostHistory.xml`, keeping only close (10), reopen (11), delete/undelete if present, edits for tags or title (3, 6), and the close-reason payload (duplicate vs other reasons). Pull close reasons and duplicate targets out of the JSON in `Comment`/`Text`. **Findings:** event counts by type and year, the close-reason breakdown, and run time.

- [x] **P08: Data quality profile.** *Done 2026-10-20: all integrity checks pass; 14.4M deleted SO posts visible via votes; comparison sites also fell sharply → prereg platform-wide test moved to log scale (deviation); SO read-only 2026-08-09 added to events.* Using DuckDB: check for duplicate IDs, orphaned answers, date ranges, and weekly question counts for each site (charted). Find odd spikes or gaps (spam waves, outages, bulk migrations) and compare totals with the counts in `Tags.xml`. Put the checks into `tests/test_data_quality.py`. **Findings:** a checklist with pass or fail for each check, the anomaly dates, and the weekly-counts chart for SO and 3 comparison sites.

- [x] **P09: SEDE reconciliation.** *Done 2026-10-20: dump matches SEDE (median diff 0.001%); SO deleted share of questions rose 33.5% (2017) → 52.9% (2026); dump slightly overstates SO decline (−4.59 vs −4.33 log points), gap to donors unchanged.* Write SEDE SQL for monthly question and answer counts per site (2019–present). Give the user the queries to run and the CSV names to save into `data/reference/sede/`. Compare those counts with the dump totals, and use SEDE's `PostsWithDeleted` to estimate how many deleted posts are missing per month. **Findings:** differences by month (%), whether the deleted-post share changed after 2022, and what that means for the size of the estimated decline.

### Phase 2: Analysis tables

- [x] **P10: Question features.** *Done 2026-10-21: 29.4M question rows (1.6 GB); account-age rule for post-question accounts; SO post-period questions longer, slower to be answered, more first-time askers (descriptive).* Build `questions.parquet`, one row per question: site, week, tags, body length, code blocks, title length, score, views, accepted answer (yes/no), answer count, time to first answer, time to accepted answer, closed and duplicate flags with dates, asker account age at the time of asking, whether it's the asker's first post, and asker reputation (current reputation only; note the bias). **Findings:** summary statistics before vs after 2022 for SO, missing-data rates, and known biases.

- [x] **P11: Tag taxonomy.** *Done 2026-10-21: 300 tags in 11 families; pre-period features (age capped for 59% of tags); 69 new tags (30 new tech / 39 versions-features; secondary split pre-registered).* Take the top 300 SO tags by question count over 2019–2021. Assign each a family (language, framework or library, cloud, data/ML, DevOps, database, mobile, tooling, other) in `data/reference/tag_families.csv`, with notes for unclear cases. Add tag age (first question date), size before 2022, and a "documentation maturity" proxy (e.g. share of questions closed as duplicates before 2022, or tag-wiki length). **Findings:** families by size, the oldest and newest tags, and the tags that were hard to classify.

- [x] **P12: User cohorts and core answerers.** *Done 2026-10-21: 6.34M SO posters; 11,156 core answerers; 1-year return 49.6% (2015) → 36.8% (2022) → 17.4% (2025); answering became less concentrated; H5 moved to placebo cohorts (deviation).* For each user: first-post month, monthly activity (asked / answered / commented), and "core answerer" status (top 1% of answers over 2019–2021). For each new-user cohort: activity by month since first post. **Findings:** cohort sizes over time, the number of core answerers, and how concentrated answers are (Gini, top-1% share) by year.

- [x] **P13: Weekly panels.** *Done 2026-10-21: 4 panels (site/tag × week/month, Parquet+CSV) with fixed-window outcomes and zero-filled periods; totals reconcile; tag counts now sparse → H2 uses a count model (deviation).* Build site × week and tag × week panels: questions, answers, new users, active askers, active answerers, % answered, median time to first answer, duplicate rate. Note that the final 8 weeks are not fully observed (answers and closures may still arrive). **Fixed-window outcomes (decided 2026-10-21):** answered within 24 h, answered within 7 days, accepted within 30 days; questions without the full window before the 2026-09-30 cut-off are excluded from those measures. Publish these as Parquet and CSV. **Findings:** panel sizes, coverage, and the incomplete weeks that were flagged.

- [ ] **P14: Exploratory analysis.** In `notebooks/01_eda.ipynb`: long-run trends (indexed to 2019 = 100) for each site group, seasonality (weekday, holidays, academic calendar), the pre-2022 slope for each site, and how the comparison sites tracked SO before 2022. Stay descriptive, with no causal claims yet. **Findings:** 4–6 charts, the pre-trend picture, and whether the comparison sites look usable.

### Phase 3: Headline effect

- [ ] **P15: Interrupted time series.** Fit a segmented regression on log weekly SO questions: trend, Fourier seasonality, holiday dummies, a level and slope break at 2022-11-28, and HAC (Newey–West) standard errors. Check autocorrelation in the residuals, and report the level and slope changes and the cumulative % gap with 95% intervals. **Findings:** the estimates table, a fitted vs actual chart, and diagnostics.

- [ ] **P16: Forecast counterfactual.** Fit ETS and Prophet on data up to 2022-11 and forecast to 2026-09 with prediction intervals. Backtest on pre-period holdouts (e.g. train to 2019, predict 2020–2022) so we can see how accurate the forecasts are. **Findings:** the % gap with intervals, backtest error, and how the two models compare.

- [ ] **P17: Synthetic control.** Use augmented synthetic control on log weekly or monthly questions with the comparison pool as donors. Report the donor weights and pre-period fit (RMSPE). Run placebos in space (each donor treated as if it were SO) and in time (fake break dates in 2019–2021), and give the permutation p-value. Check sensitivity with and without Mathematics, and with the tech sites added as donors. Add a separate difference-in-differences of SO vs ru.stackoverflow. **Findings:** the gap estimate, donor weights, the placebo chart, p-value, and the sensitivity table.

- [ ] **P18: Robustness.** Alternative break dates (Copilot GA 2022-06, GPT-4 2023-03); excluding the June–Aug 2023 strike; adding the deleted-post correction from P09; monthly vs weekly data; answers and new users as outcomes. **Findings:** a forest plot of all the estimates, and which conclusions hold up.

### Phase 4: Who, what and which tags

- [ ] **P19: Tag-level effects.** For each of the top 300 tags, estimate the post-2022 change vs its own trend (or vs the comparison group), then fit a hierarchical model (bambi or PyMC) that pools small tags toward the average. Explain the differences with tag family, age, size and documentation maturity. **Findings:** the top and bottom 15 tags with intervals, which tag characteristics matter, and shrinkage diagnostics.

- [ ] **P20: "Thin training data" test.** Do newer or niche tags decline less? Use the scatter of decline vs tag age/size with a fitted line, and a version that controls for the tag's pre-trend. Add a "post-2021 tags" subgroup (technologies that appeared after the LLM training cut-offs). **Findings:** the estimated slope with its interval, labelled outliers, and whether the hypothesis is supported.

- [ ] **P21: Question mix.** Compare 2021 with the latest year: body length, code presence, asker newness, duplicate rate, close rate, score, and % answered. Use a reweighting decomposition to separate composition (which tags) from within-tag change. **Findings:** a slope-chart table, and whether the remaining questions are "harder".

- [ ] **P22: Newcomer pipeline.** Measure new-user arrivals per month vs counterfactual, and survival curves (Kaplan–Meier) for return activity by monthly cohort; compare 2021 cohorts with 2023+ cohorts. **Findings:** the arrival gap, the retention heatmap, and median time to a second post by cohort.

- [ ] **P23: Answerers.** Primary test per the 2026-10-21 deviation: placebo cohorts (top-1% answerers of each 3-year window 2014–16 … 2019–21, share active 1–3 years later). Also track how many core answerers are still active, answers per core answerer, their share of all answers, and newly emerging top answerers after 2022. Compare with a comparison site. **Findings:** whether experts left, slowed down, or moved to fewer questions.

- [ ] **P24: Responsiveness.** Track time to first answer, % answered within 24h, and % with an accepted answer over time, with bands; account for the incomplete final weeks. **Findings:** whether the community that remains is still responsive.

- [ ] **P25: Where did help-seeking go?** (Needs a Google Cloud account with BigQuery; the free tier should cover it.) GH Archive via BigQuery: issues and Discussions opened per month for the top languages, compared with SO tag trends; plus Stack Overflow Developer Survey AI-use shares by year as context. **Findings:** whether there is evidence of displacement to GitHub, and survey AI-adoption figures.

### Phase 5: Figures and reproducibility

- [ ] **P26: Visual theme and hero chart.** Build `src/sod/viz/theme.py` (palette, fonts, annotation style; colour-blind safe; light and dark). Hero chart: weekly SO questions 2008–2026 vs the synthetic-control counterfactual band, with annotated events from P02. Export as SVG and PNG. **Findings:** the chart, plus 2–3 alternative versions for the user to choose from.

- [ ] **P27: Remaining figures.** Charts 2–7 from the plan (tag dot plot, tag-age scatter, cohort heatmap, question-mix slope chart, comparison-site small multiples, responsiveness). **Findings:** all the charts, each with the one-sentence takeaway it supports.

- [ ] **P28: Reproducibility.** Get `make all` running end to end from raw XML (and a faster `make all SAMPLE=1` on fixtures). Add tests that pin the headline estimates within a tolerance, and set up CI on the sample path. **Findings:** total run time, the pinned values, and CI status.

- [ ] **P29: Analysis validation.** Review the methods as an independent reviewer would: identification, leakage of post-period data into the counterfactual, multiple comparisons, the effect of the deleted-post and watermark issues on conclusions, and whether every claim in the draft has the estimate it needs. **Findings:** a list of issues by severity, with fixes applied or proposed.

### Phase 6: Deliverables

- [ ] **P30: Quarto article.** Write `report/index.qmd`: headline finding first, then method in plain English, results, what this doesn't show, and robustness. Cite del Rio-Chanona et al. (2024). Render to HTML. **Findings:** the article link, word count, and claims that are still weak.

- [ ] **P31: Tag lookup app.** Build an interactive page: type a tag and see its weekly trajectory, its counterfactual, and its rank among other tags. It should be a static site (e.g. Observable Framework or a single HTML file with precomputed JSON). **Findings:** the app, the bundle size, and the tags it covers.

- [ ] **P32: Published dataset.** Prepare the weekly site × week and tag × week panel for Hugging Face and Kaggle: data card, licence (CC BY-SA 4.0), attribution, column dictionary, and known limitations. Re-check the dump terms before uploading. **Findings:** files, sizes, and the draft data card; the user decides whether to upload.

- [ ] **P33: README.** Hero chart, three bullet findings, one "what this doesn't show" line, how to reproduce, and links. **Findings:** the README.

- [ ] **P34: Launch kit.** Draft the HN title and first comment, a post for Meta Stack Overflow, r/dataisbeautiful and r/programming posts, and a LinkedIn/Bluesky thread. List the questions reviewers are likely to ask, with answers. **Findings:** the drafts; nothing is posted without the user.

### Phase 7: After launch

- [ ] **P35: Living tracker.** Monthly refresh from the SEDE/API to extend the weekly panels past the dump cut-off. Re-run the headline models and figures, with a scheduled job, an "updated on" stamp on the article and app, and an alert if the new data disagrees with the dump in overlapping weeks. **Findings:** the refresh run log, the updated headline number, and any differences from the dump.

Out of scope for now (can be added later): a question-difficulty classifier.
