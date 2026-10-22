# Meta Stack Overflow

**Status:** draft. Nothing is posted without John.
**Where:** meta.stackoverflow.com, tag `[discussion]` (add `[data-dump]` and `[statistics]` if they exist). Meta readers know the site's history in detail and will check the method, so lead with the data and the questions, not the headline.
**When:** the same day as or a day after Hacker News; reply to comments for the first 48 hours.

## Title

An analysis of the 2026-Q3 data dump: how far have questions fallen beyond the pre-2022 trend, and who left?

## Body

> I've analysed the 2026-Q3 data dump (27 sites, cut-off 2026-09-30) to measure how far new Stack Overflow questions have fallen since ChatGPT, beyond the decline that was already under way. I'd value this community's view on what I may have got wrong, especially about site events I may have misread.
>
> **Main result.** Against a "synthetic control", a weighted blend of 15 non-programming Stack Exchange sites that tracked Stack Overflow closely from 2017 to November 2022, monthly questions averaged **72% below** (95% interval −76% to −68%) from December 2022 to September 2026. The gap grew each year: −34% (2023), −61% (2024), −81% (2025), −92% (2026 to September). The comparison sites fell too, −31% against their own trends, so this is Stack Overflow's fall *beyond* them.
>
> **Things you may find useful or want to challenge:**
> - **Deleted questions.** The dump leaves them out, and the deleted share rose from about 34% (2017) to 53% (2026). I used SEDE's `PostsWithDeleted` counts as a check: including deleted questions gives −71.5% instead of −72.3%.
> - **Site events.** I treated these as possible confounders: the 2023 moderator strike (dropping those months gives −74%), Staging Ground (June 2024), opinion-based questions (October 2025) and the read-only period (August 2026). Ending the analysis in September 2025, before the 2025 changes, gives −60%. If there are events I've missed that would move question counts, I'd like to know.
> - **Tags at time of asking.** Tags come from the first tag event in the post history, not today's tags, because retagging accumulates over time. Tags that were retired or merged (`excel-vba`, `flutter-layout`, `dockerfile`) are excluded by a fixed rule.
> - **Newcomers and answerers.** The share of new askers who post again within a year fell from 44% to 29% (22.6% for those arriving after Staging Ground launched). The 2019–21 top-1% answerers stayed active less than earlier cohorts, but after correcting for multiple tests, that isn't conclusive.
> - **Responsiveness.** Questions answered within 24 hours fell from 67% (2019–21) to 55% (2025). More answers now go to questions over a year old: 37% in 2025, 13% in 2019.
>
> **Method notes.** I wrote down hypotheses and decision rules before fitting any model on post-ChatGPT data, with a dated log of later changes. Everything is reproducible from the dump, and only derived counts are published, no post text or user names. The analysis does not train any model on the data.
>
> Article: https://johnpospisil.github.io/stackoverflow-decline/
> Code, pre-registration and data notes: https://github.com/johnpospisil/stackoverflow-decline
> Tag lookup: https://johnpospisil.github.io/stackoverflow-decline/app/
>
> This is an independent project, not affiliated with Stack Overflow.
