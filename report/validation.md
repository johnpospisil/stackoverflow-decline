# Analysis validation (P29)

An independent-reviewer pass over P14–P27, done 2026-10-21 before the article is written.
Numbers come from `report/qa/*_summary.json`; the new checks are in `sod.models.validation`
(`report/qa/validation_summary.json`). Severity: **High** = changes a verdict or headline claim;
**Medium** = changes how a claim must be worded; **Low** = disclose only.

## Issues

| # | Severity | Issue | Finding | Status |
|---|---|---|---|---|
| 1 | **High** | **Holm adjustment across H2–H5 had not been applied** (pre-registration section 6) | Family p-values: H2 1.00, H3 1.00, H4 0.99, H5 0.024. The smallest (H5) must clear 0.05 / 4 = 0.0125, so **none of H2–H5 is supported after adjustment**. H5 moves from "supported" to "consistent with H5, not confirmed". | Applied; deviation logged (how each family's p-value is computed was decided after the results); pinned |
| 2 | **High** | **H5's reference cohorts drift down on their own.** The pre-ChatGPT placebo cohorts' share still active falls about 2 points a year | At distance 2 the 2019–21 cohort (62.7%) is only 2.7 points below the trend extrapolation (65.5%; p = 0.08). At distance 3 it is 7.0 points below (55.2% expected vs 48.3%; p = 0.045). The "below the range" rule partly picks up that drift. | Reported; article wording: "core answerers left faster than earlier cohorts, but the evidence is not conclusive" |
| 3 | **High** | **"1.6 million questions not asked" had no interval** and counts only questions that survive in the dump | 1.57 million fewer questions than expected, Dec 2022 – Sep 2026 (range 1.21–1.99 million from the monthly 95% conformal bounds, summed, which is conservative). **Counting questions later deleted (SEDE): 3.06 million (2.45–3.75 million).** By year: 0.38 M (2023), 0.57 M (2024), 0.42 M (2025), 0.20 M (2026 to Sep). | Fixed in hero B (range + deleted count); article must say which count it uses |
| 4 | **Medium** | **The comparison sites were also hit.** Non-programming sites fell a median 31% below their own pre-trends (Philosophy, Travel and Movies are the exceptions) | The synthetic control measures Stack Overflow's fall **relative to** sites that also fell, so −72% is the *extra* fall beyond them, not Stack Overflow's total fall due to AI (that is likely larger). | Hero A subtitle no longer says the donors were "barely touched"; article must say "relative to comparable sites" |
| 5 | **Medium** | **Average of monthly gaps vs share of all questions.** −72% is the mean monthly log gap; months late in the period (gap −92%) weigh as much as early ones | Over the whole period, total questions were **53% below** the counterfactual (1.41 M vs 2.98 M). Yearly gaps: 2023 −34%, 2024 −61%, 2025 −81%, 2026 −92%. | Hero A title now says "have averaged 72% below"; article leads with the yearly gaps (already planned) |
| 6 | **Medium** | **Chart titles that overstate** | fig4 "Newcomers stopped coming back": 12-month return fell from 44% to 29%, not to zero, so it is now "Fewer newcomers come back". fig6 "The collapse is specific to programming Q&A": every site fell (non-programming sites to 4–21% of their 2019 level, except Philosophy at 78%), so it is now "Every site fell, but programming Q&A fell furthest". | Fixed |
| 7 | **Medium** | **Time placebos show a consistent positive error** (+15% to +24% at fake breaks in 2019–2021) | Before ChatGPT, the synthetic control under-predicted Stack Overflow by 15–24% over 1–3 years, so the counterfactual tends to run *low*. The error has the opposite sign to the effect, so it makes −72% conservative, but it also shows that extrapolation error is larger than the conformal band (about ±4 points) suggests. | Article states it; the robustness range (−60% to −74%) is the honest uncertainty |
| 8 | **Medium** | **H1 interval reading decided after the results** (deviation A) | Already logged. With the constant-effect interval, H1 fails the interval criterion. Everything else (rank 1 of 16, all 15 robustness variants, ITS/ETS/Prophet at −79% to −83%) points the same way. | Article states it next to H1 (planned) |
| 9 | Low | **Leakage of post-period data into counterfactuals** | Synthetic control: weights and demeaning use pre-period months only ✔. ITS: the joint fit lets post weeks inform seasonality; refitting on pre-period weeks only gives −83.4% vs −83.4% (post-COVID trend: −79.5% vs −79.3%) ✔. Tag model: fixed earlier with the per-tag post-period line ✔. New tags: selected on total questions (≥ 200), an outcome-based rule, but the lifecycle reference tags are selected the same way, and the pre-ChatGPT calibration gives −9% ✔. | No change |
| 10 | Low | **Deleted posts** (missing from the dump; deleted share 34% in 2017 → 53% in 2026) | Synthetic control with deleted questions included: −71.5% (vs −72.3%). H3: Lee bounds flip the code-share result (in the H3 table). The dump slightly overstates Stack Overflow's raw fall, but not the gap to donors (P09). | No change; disclosed |
| 11 | Low | **Watermarking** | No watermark rows in any site (P01; full Stack Overflow scan in P05). Checksums match the community list; the official list was not yet published. | Recheck the official checksums before publishing (DATA.md section 5) |
| 12 | Low | **Placebo-in-space p = 0.0625 is the smallest possible with 16 sites** | It meets the pre-registered rule ("Stack Overflow ranks first"), but it is not "p < 0.05". | Article wording: "ranked first of 16" |
| 13 | Low | **Other platform changes** confound late months: opinion questions (2025-10), AI Assist (2025-12), read-only period (2026-08) | The pre-registered late-period check (to 2025-09) gives −60%, still far beyond −10%. Acceptance series break at 2025-10 (E1). | Report both, as pre-registered |
| 14 | Low | **Developer Survey respondents are self-selected Stack Overflow visitors** (about 90k → 34k), and 2025 asks about frequency | AI-use shares describe survey respondents, not all developers; 2026 is not comparable. | Article wording |
| 15 | Low | **The ru.stackoverflow difference-in-differences** (−21%, interval −33% to −7%) | Lower exposure, not zero: ChatGPT was reachable from Russia via VPN, so this is a lower bound on the contrast. | Article wording |

## Claim → estimate table (for P30)

Every headline claim and the estimate behind it. Anything not here needs an estimate before it goes in the article.

| Claim | Estimate (95% interval or range) | Source |
|---|---|---|
| Questions averaged 72% below what comparable sites predict (Dec 2022 – Sep 2026) | −72.3% (monthly conformal −75.7% to −68.5%; 42 of 46 months exclude 0); ranked 1 of 16 | synth_summary |
| The gap grew every year | 2023 −34%, 2024 −61%, 2025 −81%, 2026 −92% | synth_summary `att` |
| About 1.6 million fewer questions than expected | 1.57 M (1.21–1.99 M); 3.06 M (2.45–3.75 M) counting deleted questions | validation_summary |
| Every method agrees | Synthetic-control variants −60% to −74%; ITS −83% / −79%; ETS −83%; Prophet −81% | robustness_summary, its, forecast |
| Programming Q&A fell furthest | Donor median own-trend gap −31% vs Stack Overflow −84% (ratio 0.21) | synth_summary `platform_wide` |
| Every one of the 297 tags fell against its own trend | All 297 intervals below 0; median −86% (iOS −58% to Dart −98% among the top 50) | tags_summary, tag_effects.csv |
| Tags created after the first ChatGPT training cut-off held up better | −49% (−55% to −44%) vs top-300 median −85% | thin_data_summary |
| Older tags fell *less* (opposite to H2) | Age slope +0.41 per SD (+0.34 to +0.48) | thin_data_summary |
| Questions got longer within topic | Median body +518 characters (+507 to +529); Lee bounds +309 to +695 | question_mix_summary |
| Fewer newcomers come back | 12-month return 44.0% → 28.5% (difference −15.5 points, −15.6 to −15.3) | newcomers_summary |
| Core answerers dropped out faster than earlier cohorts (not confirmed after Holm) | 62.7% / 48.3% still active at +2 / +3 years vs reference 69.3–75.6% / 61.2–68.3%; Holm-adjusted p = 0.095 | answerers, validation |
| Fewer questions get answered within a day | 67.4% (2019–21) → 54.7% (2025) | responsiveness_summary |
| Answers take longer | Median 0.7 h (2019) → 2.8 h (2025), among questions answered within 7 days | responsiveness_summary |
| No sign that help-seeking moved to GitHub issues | Median flagship-repo issue index 55 (2025-01..05) vs SO tag index 9; GitHub overall 140 | github_summary |
