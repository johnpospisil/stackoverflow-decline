# Pre-registration

**Project:** What happened to Stack Overflow? (see [04-stackoverflow-decline.md](04-stackoverflow-decline.md))
**Written:** 2026-10-19, before any model is fitted. **Locked:** at the git commit that adds this file (tag `prereg-v1`).
**Rule:** after locking, this file is only appended to, under [Deviations](#9-deviations). Every result reported in the article is labelled *pre-registered* or *exploratory*.

## 0. What had been seen before writing this

- **No outcome data from the dump has been analysed.** At lock time the raw XML had been downloaded, hashed and scanned for watermarks (P01). No counts of questions, answers or users over time have been computed or plotted.
- **Prior knowledge (public):** del Rio-Chanona, Laurentsyeva & Wachs (PNAS Nexus, 2024) report a roughly 25% relative drop in SO posting within six months of ChatGPT, compared with platforms where ChatGPT was less accessible. Press reports since 2023 describe large declines in SO question volume. So a decline is expected; the open questions are its **size beyond the existing trend**, whether it is **specific to programming**, and **who and what** it affects.

## 1. Research questions and hypotheses

| ID | Hypothesis (direction stated in advance) | Status |
|---|---|---|
| **H1** (primary) | After ChatGPT, new SO questions fell **below** what the pre-2022 trend and the comparison sites predict | Confirmatory |
| H2 | The decline is **larger for older, larger, well-documented tags** and **smaller for tags created after 2021-09-30** (after the training cut-off of the first ChatGPT models) | Confirmatory |
| H3 | Questions that remain are **"harder"**: within tag, longer bodies, more code, lower duplicate-close rate, smaller share from first-time askers | Confirmatory |
| H4 | **New-asker arrivals fell more than total questions**, and askers who arrived in 2023 or later return less often than those who arrived in 2019–2021 | Confirmatory |
| H5 | The **core answerer group shrank**: a smaller share of 2019–2021 top-1% answerers is still active each year after 2022 than before 2022 | Confirmatory |
| E1 | Responsiveness (time to first answer, % answered) | Exploratory |
| E2 | Displacement to GitHub (GH Archive, P25) | Exploratory |
| E3 | Tech sites also exposed to AI (Super User, Server Fault, etc.) decline more than the non-programming comparison sites | Exploratory |

## 2. Data and sample

- **Source:** Stack Exchange data dump, 2026-Q3 release (cut-off 2026-09-30), 27 sites ([DATA.md](DATA.md)). Posts that were deleted before the dump date are not included.
- **Unit of analysis:** site × calendar month (primary) and site × week (Monday to Sunday, UTC).
- **Pre-period:** 2017-01 to 2022-11 (the ChatGPT week starts Monday 2022-11-28, so November 2022 counts as pre-period; robustness drops it).
- **Post-period:** 2022-12 to 2026-09. September 2026 is used only if the latest `CreationDate` in SO `Posts` is on 2026-09-30; otherwise the post-period ends 2026-08. For weekly data, the last week used is the last complete week.
- **Excluded from fitting:** 2020-03-11 to 2020-06-30 (COVID lockdown spike), modelled with an indicator, not deleted.
- **Not excluded in the primary analysis:** the moderator strike (2023-06-05 to 2023-08-02). Excluding it is a robustness check.
- **Treated unit:** stackoverflow.com.
- **Donor pool (comparison sites):** the 15 non-programming sites in `config.SITE_GROUPS["donor"]`: math, physics, chemistry, biology, english, philosophy, history, cooking, diy, travel, bicycles, gaming, scifi, movies, rpg.
- **Never donors:** SO in other languages, the tech sites also exposed to AI, Meta Stack Overflow.

## 3. Primary outcome and estimand

- **Outcome:** number of new questions (`PostTypeId = 1`) created in the month, by `CreationDate` (UTC).
- **Transformation:** natural log, then each site's series minus its own pre-period mean, so sites of different sizes can be compared.
- **Estimand (H1):** the average gap between SO's log questions and its counterfactual over all post-period months:
  `ATT = mean over post months of [log Y_SO − log Ŷ_SO(0)]`.
  Reported as a percentage: `100 × (exp(ATT) − 1)`. Also reported per year (2023, 2024, 2025, 2026 to date).
- **Smallest effect of interest:** −10%. A decline smaller than 10% beyond trend and comparison sites is treated as not substantively meaningful, even if statistically distinguishable from zero.

## 4. Primary model and inference

**Estimator: synthetic control** (`pysyncon.Synth`). Fit on the demeaned log monthly outcomes for the pre-period. Weights are non-negative and sum to 1 across the 15 donors.

**Inference:**
1. **Interval:** 95% conformal confidence interval for the ATT (Chernozhukov, Wüthrich & Zhu, 2021; `Synth.confidence_interval(method="conformal")`).
2. **Placebo-in-space test:** refit with each donor as the "treated" site. The p-value is SO's rank on the post/pre RMSPE ratio among 16 sites. **The smallest possible p is 1/16 = 0.0625**, so the threshold is "SO ranks first".
3. **Placebo-in-time test:** fake break dates at 2019-11, 2020-11 and 2021-11, using only pre-period data. None should show a gap as large as the real one.

**Pre-period fit requirement:** if SO's pre-period RMSPE is more than **2×** the median donor's placebo pre-RMSPE, the synthetic control is judged not to fit. In that case the **interrupted time series (section 5) becomes the primary estimate**, and the switch is reported.

### Decision rule for H1

| Result | Conclusion |
|---|---|
| ATT ≤ −10%, 95% interval excludes 0, SO ranks first in the space placebo, and no time placebo is as large | **H1 supported** |
| Interval excludes 0 but the ATT is between −10% and 0 | Decline beyond trend is **real but small** |
| Interval includes 0, **or** SO does not rank first in the space placebo | **H1 not supported** (null) |
| The comparison sites, against their own pre-trends, fall by within 10 percentage points of SO's fall | Decline is **platform-wide, not programming-specific**; report as refuting the programming-specific version of H1 |

## 5. Supporting estimators (all reported; they don't override section 4)

1. **Interrupted time series (weekly, SO only).** Model log weekly questions with a linear trend, Fourier terms for yearly seasonality (K = 4), holiday-week dummies (Christmas–New Year, US Thanksgiving), the COVID indicator, and a level and slope change at 2022-11-28. Newey–West standard errors with 8 lags. Report the level change, slope change and cumulative % gap.
2. **Forecast counterfactual.** ETS (statsmodels) and Prophet trained to 2022-11, forecast to the end of the post-period with 95% prediction intervals. Accuracy checked by training to 2019-11 and predicting 2019-12 to 2022-11.
3. **SO vs ru.stackoverflow difference-in-differences.** Monthly log questions, two-way fixed effects. This is a lower-exposure comparison, since ChatGPT was not officially available in Russia.

**Consistency check:** if the supporting estimators disagree in sign with the primary estimate, the article must say so prominently.

## 6. Secondary hypotheses: tests and decision rules

- **H2 (tags).** Tag sample: top 300 SO tags by 2019–2021 question count. Per-tag outcome: log monthly questions vs the tag's own pre-trend, extended into the post-period.
  - Model: a hierarchical (partial-pooling) model across tags, with predictors log tag age (years since first question), log size before 2022, tag family, and a documentation-maturity proxy (fixed in P11 before tag outcomes are examined). Also an indicator for tags created after 2021-09-30, analysed separately because there will be few such tags among the top 300; their sample is "all tags with ≥ 200 questions".
  - **Supported** if the 95% credible interval for the tag-age slope is negative (older tags decline more) **and** the post-2021 tag group's decline is smaller than the average tag's.
- **H3 (question mix).** Compare 2021 with the latest full post year (2025). Within-tag changes use a reweighting decomposition that holds the tag mix at 2021 shares.
  - **Supported** if at least 3 of the 4 measures move in the predicted direction with 95% intervals excluding 0: median body length, % with code blocks, duplicate-close rate, % of questions from first-time askers.
- **H4 (newcomers).**
  - Part (a): the post-period gap in first-time askers is larger in magnitude than the gap in all questions, using the same synthetic-control setup.
  - Part (b): Kaplan–Meier probability of a second post within 3 and 12 months, 2023+ cohorts vs 2019–2021 cohorts.
  - **Supported** if (a) holds and (b) is lower at both horizons with 95% intervals excluding 0.
  - **Caveat fixed in advance:** Staging Ground (2024-06-04) changes how new askers' questions are posted. Results are shown for 2023-01 to 2024-05 separately.
- **H5 (answerers).** Core answerers are the top 1% of answerers by 2019–2021 answer count. Outcome: share of them active (≥ 1 answer) in each year 2017–2026.
  - **Supported** if the post-2022 yearly share falls below the 2017–2021 trend line extended forward, by more than that line's 95% prediction interval.
- **Multiple comparisons.** H2–H5 are four confirmatory families. Their decision p-values or intervals are adjusted with **Holm's method at α = 0.05**. Per-tag estimates in H2 come from the pooled model and get no separate p-values; when tags are ranked, the text describes them as estimates with intervals, not as "significant".

## 7. Robustness checks (all pre-specified; reported in a forest plot)

1. Alternative break dates: Copilot GA (2022-06) and GPT-4 (2023-03).
2. Exclude the moderator strike window.
3. Pre-period starting in 2014 instead of 2017.
4. Weekly instead of monthly synthetic control.
5. Donor pool variations: without Mathematics; leave-one-donor-out (15 refits); adding the tech sites as donors.
6. Augmented synthetic control (`pysyncon.AugSynth`, ridge).
7. **Late-period sensitivity (decided 2026-10-19):** end the post-period at **2025-09** to avoid SO's own 2025–26 changes (opinion-based questions from 2025-10, AI Assist 2025-12, curation changes). The full-period and pre-2025-10 estimates are always reported together.
8. Deleted-post correction: rescale monthly counts using the deleted-post share from SEDE `PostsWithDeleted` (P09), and refit.
9. Answers and new users as alternative outcomes.
10. November 2022 dropped from the pre-period.

**Any check that flips the H1 conclusion** must be reported in the article's main text, not only in an appendix.

## 8. What would make the main finding wrong

- The decline after 2022 is explained by the pre-2022 trend alone (ITS slope and level changes not distinguishable from zero, and the synthetic-control interval includes 0).
- Comparison sites fall just as much, which points to a platform-wide cause.
- The decline starts **before** ChatGPT: the time placebos (2019–2021) show gaps of similar size, or the gap opens at the Copilot GA date and doesn't deepen after ChatGPT.
- The effect disappears once deleted posts are accounted for (robustness check 8).

## 9. Deviations

*(Append dated entries here. Each entry: what changed, why, and whether it was decided before or after seeing outcome data.)*

### 2026-10-20: Tag definition for H2 and tag panels (clarification)

- **What:** tag-level analyses (H2, tag × week panels, the tag taxonomy) use each question's **tags at the time of asking**: the initial-tags event, PostHistory type 3. Current `Posts.Tags` is used only as a fallback for the 214 Stack Overflow questions (0.001%) without that event.
- **Why:** questions keep being retagged for years (5.26M retag events on Stack Overflow). Older questions have had more time to be retagged than recent ones, so current tags would create a time trend in tag counts unrelated to ChatGPT.
- **When:** decided **before any outcome data was examined**. At this point only ingest counts and missing-value rates had been computed (P05–P07); no counts by time period.

### 2026-10-20: "Platform-wide decline" test moved to the log scale (deviation)

- **What changed:** section 4's last decision row ("comparison sites fall by within 10 percentage points of SO's fall") is replaced by a log-scale rule, the same scale as the primary estimand. For each donor site, fit the section 5.1 interrupted time series on monthly log questions and take its average post-period log gap against its own pre-trend. The decline is called **platform-wide** if the **median donor log gap is at least 0.8 × Stack Overflow's log gap** (both measured the same way). Otherwise it is **programming-specific**. The percentage-point version as originally written is also reported, labelled "original rule".
- **Why:** percentage-point differences compress near −100%. In the raw counts (Sep–Nov 2022 vs Jul–Sep 2026), Stack Overflow fell 98-fold (−99.0%) and Mathematics 10-fold (−90.0%), only 9 percentage points apart. The original rule would therefore call almost any large decline "platform-wide", whatever the relative size.
- **When:** decided **after seeing descriptive monthly counts in P08** (raw before/after changes per site), **before any model was fitted** and before any trend-adjusted estimate was computed.

### 2026-10-21: H2 tag features fixed (P11; required by section 6)

- **Documentation-maturity proxy:** share of the tag's 2019–2021 questions that were closed as duplicates (`dup_share_2019_2021`). A high share means new questions were often already answered on the site. Chosen over tag-wiki length because wikis are edited after the break.
- **Tag age:** years from the tag's first Stack Overflow question to 2022-11-30. **Size:** number of 2019–2021 questions (tags at time of asking). Also recorded but not a pre-registered predictor: `stock_to_2021_09`, questions before the training cut-off (exploratory only).
- **Files:** `data/reference/tag_families.csv` (300 tags, 11 families), `data/reference/tag_features.csv`, `data/reference/tags_new_post2021.csv` (69 tags first used after 2021-09-30 with ≥ 200 questions).
- **Note on power:** 177 of the 300 tags (59%) were in use when Stack Overflow launched, so their age is capped at about 14.3 years. The age test therefore has limited variation, and the new-tag comparison carries more of the H2 "thin training data" test.
- **When:** fixed **before any tag-level outcome was examined**. No tag counts after 2021 were computed except each new tag's total question count, which the pre-registered ≥ 200 threshold requires.

### 2026-10-21: H2 secondary split of new tags (addition)

- **What:** the pre-registered new-tag comparison (all 69 tags first used after 2021-09-30 with ≥ 200 questions) stays the **primary** H2 new-tag test. A **secondary** comparison is added: `kind = new` (30 tags of genuinely new technology) vs `kind in (version, feature)` (39 tags for new versions or features of existing technology), as classified in `data/reference/tags_new_post2021.csv`. Prediction: genuinely new technology declines less than new versions/features.
- **Why:** new versions of well-known technology (e.g. `.net-8.0`, `python-3.11`) are not "thin training data" in the intended sense.
- **When:** decided **before any tag-level outcome was examined**.
