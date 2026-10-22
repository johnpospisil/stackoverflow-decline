# Questions reviewers are likely to ask

Short answers for comment threads, each with where the evidence is. Numbers match the article (`report/qa/*.json`).

**1. "Stack Overflow was dying before ChatGPT. Isn't this just the trend?"**
That's the main thing the analysis controls for. The synthetic control tracks Stack Overflow's own pre-2022 path, decline included. A trend-only model (interrupted time series) gives −83% beyond the extended trend, and −79% using only the steeper post-COVID trend. Fake break dates in 2019–2021 give *positive* gaps (+15% to +24%), not falls.

**2. "Other Stack Exchange sites fell too. Isn't it platform-wide?"**
They did fall: the median non-programming site was −31% against its own trend. Stack Overflow was −84% on the same measure. The pre-registered rule calls a decline platform-wide if the comparison sites fall at least 0.8 times as much (log scale); the ratio is 0.21. So the fall is mostly programming-specific, and −72% is Stack Overflow's fall *beyond* similar sites. Its total loss to AI is probably larger.

**3. "How do you know it was ChatGPT and not Copilot, or Stack Overflow's own changes?"**
We don't, and the article says so. A break at Copilot's release (June 2022) gives −67%, at GPT-4 (March 2023) −74%. "AI coding tools generally" fits better than "ChatGPT specifically". Stack Overflow's own changes are checked separately: dropping the 2023 strike months gives −74%, and ending in September 2025 (before opinion questions and AI Assist) gives −60%.

**4. "The dump leaves out deleted posts."**
Yes. The deleted share rose from about 34% to 53%. Using SEDE counts that include deleted questions, the estimate is −71.5% instead of −72.3%. Deleted posts matter more for the question-mix results, which use bounds for them (Lee bounds).

**5. "The comparison sites could be affected by AI too."**
They probably were (see 2). That makes −72% a conservative estimate of the fall due to AI, not an inflated one. Three methods that use only Stack Overflow's own history give −81% to −83%.

**6. "Why is the interval −76% to −68% when the yearly gaps range from −34% to −92%?"**
The interval is for the *average* gap: the per-month 95% bounds averaged. A stricter test that assumes one constant effect in every month gives −15% to +62%. That assumption fails, because the gap grew from 0 to −92%. I chose the per-month reading after seeing both, and logged it as a deviation. Under the constant-effect reading, the interval criterion for H1 would fail; every other check points the same way.

**7. "72% of what? Stack Overflow got 1.4 million questions against 3 million expected, which is 53%."**
Both are right. −72% is the average monthly gap (each month weighs the same). −53% is the shortfall in total questions over the whole period, where 2023's large volumes dominate. The article gives both, and the yearly gaps.

**8. "Where did the questions go? Discord, GitHub, Reddit?"**
GitHub issues in 20 major projects' repositories drifted down rather than up, so there's no sign of a shift there. Discord, Reddit and chatbot use aren't observable in this data. Stack Overflow's own survey shows AI tool use among respondents rising from 44% (2023) to 78% (2025), but respondents are a self-selected group.

**9. "Were the remaining questions harder?"**
Mixed. Within topics, questions got much longer (+518 characters at the median) and slightly more often include code. Duplicate closures and the share from first-time askers didn't fall. The pre-registered test needed 3 of 4 measures; it got 2, so it's not supported.

**10. "Which tags fell most?"**
Data tags (pandas, dataframe) fell most and mobile tags (iOS, Android, Kotlin) least, on both the model and plain counts. Exact rankings depend on the trend assumption: tags that were growing fast before 2022 (Flutter, Next.js) get steep expected lines. The tag lookup shows both numbers.

**11. "Didn't you just go looking for significant results?"**
The hypotheses, decision rules and multiple-comparison correction were locked before any model saw post-ChatGPT data (git tag `prereg-v1`). Every later change is in a dated log saying whether it came before or after the results. Four of the five hypotheses are reported as not supported.

**12. "Isn't using the Stack Overflow dump to study AI ironic, given the LLM-training terms?"**
This project doesn't train any model. It publishes only derived counts, no post text or user names, under CC BY-SA 4.0 with attribution.

**13. "Is the 2026 dump watermarked or altered?"**
File hashes match the community-maintained checksum list. A full scan found no rows matching known watermark patterns. The official checksums should be compared once Stack Exchange publishes them.

**14. "Synthetic control with 15 donors and a smallest possible p-value of 1/16 = 0.0625?"**
Yes, the placebo test can't reach p < 0.05 with 16 sites. The pre-registered rule is "Stack Overflow ranks first", which it does. The other evidence is the interval and the agreement across methods.

**15. "Can I check this myself?"**
`make all SAMPLE=1` runs the whole pipeline on a synthetic dump in about 4 minutes. `make all` rebuilds everything from the real dump in about 2.5 hours. The weekly and monthly panels are published as a dataset.
