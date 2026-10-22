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

### 2026-10-21: H5 tested with placebo cohorts (deviation)

- **What changed:** H5 no longer compares 2023–2026 core-answerer activity with a 2017–2021 trend line. Instead, for every 3-year window W from 2014–2016 to 2019–2021, define that window's core answerers (top 1% of answerers by answer count in W) and measure the share still active (≥ 1 answer) 1, 2 and 3 years after W ends. Windows ending 2016–2019 (follow-up entirely before ChatGPT) give the normal attrition at each distance. H5 is **supported** if the 2019–2021 cohort's share active at distances 2 and 3 (2023, 2024) falls below the range of the pre-ChatGPT cohorts at the same distances. The 2020–2022 and 2021–2023 windows are also shown, as partly treated. The original version is reported, labelled "original".
- **Why:** core answerers are selected for high activity in 2019–2021, so their activity falls afterwards even if nothing changes (regression to the mean). The original comparison builds that fall in.
- **When:** decided **after seeing descriptive P12 counts** (core answerers active per year), **before any H5 model or test was run**.

### 2026-10-21: H2 per-tag outcome modelled as counts (deviation)

- **What changed:** H2's per-tag outcome is monthly question **counts** in a hierarchical **negative binomial** model (log link) with each tag's own intercept and pre-trend, a post-2022 level change per tag partially pooled across tags, and the same predictors as section 6. The estimand is unchanged: each tag's post-period percentage change against its own extended pre-trend (exp(coefficient) − 1). The decision rule is unchanged. The original log-outcome model (log(count + 1)) is reported as a sensitivity check, labelled "original".
- **Why:** in 2026, 15% of top-300 tag-months and 71% of new-tag months have **zero** questions, and the median top-300 tag has about 4 questions a month. log(0) is undefined, and log(count + 1) or dropping zero months biases small counts.
- **When:** decided **after seeing aggregate sparsity in the P13 panels** (zero shares and median counts across all tags), **before any per-tag decline was estimated or ranked**.

### 2026-10-21: Post-COVID pre-trend sensitivity for the interrupted time series (addition)

- **What:** the interrupted time series (section 5.1) is also fitted with the sample starting **2020-07-06** (the first full week after the COVID exclusion window), so the counterfactual trend comes only from the post-COVID pre-period. Labelled **exploratory**; it is reported next to the pre-registered fit and does not replace it.
- **Why:** P14 (descriptive) showed Stack Overflow's pre-ChatGPT decline speeding up from about −9% a year (2017–2019) to −14% a year (2020-07 to 2022-11). A single trend from 2017 would then understate the counterfactual decline and overstate the effect.
- **When:** decided after the descriptive P14 slopes, **before any interrupted time series or other model was fitted on post-period data**.

### 2026-10-21: H1 interval read from monthly conformal intervals (deviation, decided after seeing results)

- **What changed:** section 4's "95% conformal confidence interval for the ATT" is read as the **average of the per-month 95% conformal bounds** from `pysyncon` `Synth.confidence_interval(method="conformal")`, the function named in section 4. The H1 criterion "interval excludes 0" uses this interval. These averaged bounds are approximate; they are not an exact 95% interval for the average. The number of post months whose own interval excludes 0 is reported next to it. The alternative reading, a Chernozhukov–Wüthrich–Zhu test inversion for **one constant effect** over all post months, is reported in the appendix, labelled "constant-effect interval".
- **Why:** the constant-effect test assumes the same effect in every post month. Stack Overflow's gap grew steadily from about 0 to −3 log points, so that assumption fails: the constant-effect interval for the whole post-period (−15% to +62%) does not contain its own point estimate (−72%). On simulated data with a truly constant effect, the same code rejects zero (p = 0.009) and covers the true value, so the problem is the assumption, not the code.
- **When:** decided **after seeing the P17 results**, including that the H1 verdict differs between the two readings (monthly average: supported; constant-effect: not supported on the interval criterion). The article states this openly, next to the H1 result.

### 2026-10-21: H2 tag model gets a per-tag post-period line (clarification)

- **What:** in the H2 negative binomial model, each tag's post-period term is a line (level + slope, both partially pooled) instead of a single level shift. The line is centred at the middle of the post-period, so the tag's coefficient is its **average log gap against its own pre-trend**, the same measure as the headline estimate, reported as exp(coefficient) − 1. The predictors (age, size, documentation maturity, family) act on that coefficient, as before.
- **Why:** with a single level term, the tag's trend parameter is also fitted to post-period months. The decline kept steepening after 2022, so post-period data pulled each tag's "pre-trend" down and shrank its estimated change (Python: −50% instead of −92%). The pre-registered wording is "the tag's own pre-trend, extended into the post-period"; only a free post-period line keeps the trend fitted on pre-period data alone. Per-tag results now match a simple per-tag interrupted time series (e.g. Python −92% vs −92%, Java −80% vs −80%).
- **When:** found in a **30-tag smoke test** (sampler check) before the full model was run, after seeing the estimates for 10 of the largest tags. No predictor effects, rankings or H2 tests had been computed.

### 2026-10-21: Retired tags excluded from H2 (data-quality rule)

- **What:** a tag is excluded from H2 analyses if, at some month, its mean over the previous 6 months was at least 20 questions and **every one of the next 6 months is below 5% of that mean**. That is the signature of Stack Overflow retiring, merging or renaming a tag, not of askers leaving. Excluded: `excel-vba` (2020-08), `flutter-layout` (2022-12), `dockerfile` (2025-06) from the top 300; `apache-age` (2023-11), `apache-iotdb` (2024-05) from the 69 post-2021 tags. Results with them included are reported as a sensitivity check.
- **Why:** an abrupt drop to zero is a tag-system event. flutter-layout, for example, went from 2,804 questions in 2022 to zero in every later month and topped the "fell most" list at −100%.
- **When:** decided after the P19 tag model (which showed flutter-layout as the extreme), **before the H2 test (P20)**: no age, new-tag or version/feature comparison had been computed.

### 2026-10-21: How the post-2021 tags' decline is measured (clarification)

- **What:** section 6 says the post-2021 tag group must decline less than the average tag but does not say how a tag without a pre-period is measured. Decided method, a **lifecycle benchmark**:
  - **Reference tags:** Stack Overflow tags first used 2014-01 to 2017-11, so their first 60 months end before ChatGPT.
  - **For each post-2021 tag:** its follow-up F runs from its first full month to 2026-09, and its **anchor** is its mean questions in months 1–3 of life (month 0 is partial). The matched references are tags with at least 200 questions within their own first F months (the same selection as the new-tag sample) and an anchor within ×/÷2 of the new tag's (widened to ×/÷3 if fewer than 10 match).
  - **Counterfactual at month k ≥ 4:** anchor × the geometric mean of the references' month-k / anchor ratios.
  - **Tag's gap:** log(Σ actual / Σ counterfactual) over months 4 to F−1, reported as exp(gap) − 1.
- **Test:** the group statistic is the median new-tag gap. It is compared with the median top-300 tag's gap from the H2 model (each against its own counterfactual), using a bootstrap 95% interval (new tags resampled; top-300 median from the posterior draws). Part (b) of H2 is supported if the new tags' median gap is **smaller in magnitude** and the interval for the difference excludes 0. The secondary split (kind = new vs version/feature) uses the same gaps.
- **Calibration check:** the same method applied before ChatGPT (tags first used 2017-06 to 2018-11, followed to 2022-11, references 2014-01 to 2016-12) should give a median gap near 0.
- **Caveat stated in advance:** the two groups' counterfactuals are built differently (lifecycle benchmark vs own pre-trend), so the comparison is approximate.
- **When:** decided **before any new-tag outcome was computed**. P19's top-300 results (median −86%) were known at the time.

### 2026-10-21: H3 measures defined, plus a deleted-question bound (clarification and addition)

- **Measures** (the section 6 wording, made exact):
  - body length = median `body_chars` (whole body, code included)
  - code = share with at least one code block (`n_code_blocks` ≥ 1)
  - duplicate-close rate = share **first closed as a duplicate (close reason 101) within 30 days** of asking, the same window for both years
  - first-time askers = share of questions that are the asker's first post on Stack Overflow, among questions whose asker is not deleted
- **Tag-mix reweighting:** each question spreads weight 1/n_tags over its tags (top-300 tags, plus one "other" bucket). 2025 questions are reweighted so the tag shares equal 2021's. Within-tag change = reweighted 2025 minus 2021; composition change = actual 2025 minus reweighted 2025.
- **Intervals:** 95% Poisson bootstrap, 200 replicates. The section 6 decision rule is unchanged (at least 3 of 4 within-tag changes in the predicted direction with intervals excluding 0).
- **Addition (sensitivity, not part of the decision rule):** the share of Stack Overflow questions later deleted rose from 41.8% (2021) to 50.8% (2025), and deleted questions are missing from the dump. **Lee bounds** trim the 2021 sample by the survival difference, (0.582 − 0.492) / 0.582 = 15.5%, from each end of each measure, to show how much of each change could come from the extra deletions.
- **When:** decided **before any 2021-vs-2025 comparison was computed for P21**. P10's descriptive before/after summaries (2019–22 vs 2023–26; e.g. first-time askers 20.8% → 25.3%) had been seen.

### 2026-10-21: H4 measures defined (clarification)

- **Part (a):** the monthly count of **first-time askers** per site is the number of questions that are the asker's first post (question or answer) on that site. Questions whose owner was deleted are excluded, because their status is unknown. "Larger in magnitude than the gap in all questions" is tested directly, in the section 4 synthetic-control setup (same donors, periods, demeaning, COVID exclusion), on the **log share of questions from first-time askers**, log(first-time askers / questions). Part (a) holds if that ATT is below 0 and its averaged monthly 95% conformal interval excludes 0. The ATTs for first-time askers alone and all questions alone are reported next to it.
- **Part (b):** the population is users whose **first post on Stack Overflow is a question**, grouped by the month of that post. The event is a second post of any kind; follow-up is censored at 2026-09-30. Kaplan–Meier probability of a second post within 91 and 365 days, for 2023-01 to 2026-09 arrivals vs 2019-01 to 2021-12 arrivals, with 95% intervals for the difference (Greenwood standard errors). Also shown separately as fixed in advance: 2023-01 to 2024-05 and 2024-06 onward (Staging Ground).
- **Descriptive extra (not part of the decision rule):** first-time askers split by account age at their first post, "new account" (≤ 7 days) vs "older account" (> 7 days). P21 showed the median asker account age rising from 641 to 1,908 days.
- **When:** decided **before any H4 estimate was computed**. Known beforehand: P12 return rates, P18's new-poster synthetic control (−64%), and P21's first-time-asker shares (22.5% in 2021, 22.6% in 2025, unweighted).

### 2026-10-21: Decision p-values for the Holm adjustment across H2–H5 (clarification, decided after seeing results)

- **What:** section 6 requires Holm's method across H2–H5 but did not define each family's decision p-value, and the H5 placebo-cohort rule (deviation above) is a range comparison with no p-value. Defined in P29 (`sod.models.validation`):
  - a family whose rule needs several parts to hold gets the **largest** part p-value (intersection–union test); H3's "at least 3 of 4" rule gets the **third-smallest** of its four measure p-values;
  - part p-values are one-sided in the predicted direction: from the stored 95% intervals by a normal approximation (H3 bootstrap, H4 conformal and Greenwood intervals), or the posterior tail probability for the Bayesian H2 age slope;
  - **H5:** the 2019–2021 cohort's share active is compared with the four pre-ChatGPT reference cohorts at distances 2 and 3 using a **t prediction interval around the reference mean** (3 df); the family p-value is the larger of the two. A trend-extrapolation version (the reference cohorts drift down about 2 points a year) and the exact rank p (1 of 5, so p = 0.2) are reported next to it.
- **Result:** family p-values H2 1.00, H3 1.00, H4 0.99, H5 0.024. Holm compares the smallest (H5) with 0.05 / 4 = 0.0125, so **no H2–H5 hypothesis is supported after adjustment**. H5 changes from "supported" (P23, unadjusted rule) to **"consistent with H5 but not confirmed after the pre-registered multiple-comparison adjustment"**. Under the trend version, p = 0.082. With only four reference cohorts, the H5 design could not have reached the Holm threshold with the rank test at all.
- **When:** decided **after all H2–H5 results were known** (P20–P23). The adjustment itself was pre-registered; only the way each family's p-value is computed was decided now. Every alternative is reported, and none of them would support H5 after Holm.
