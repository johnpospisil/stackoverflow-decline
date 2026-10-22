# Reddit

**Status:** drafts. Nothing is posted without John. Check each subreddit's current rules on the day: both limit self-promotion, so post from an account with other activity, and don't cross-post the same day.

## r/dataisbeautiful

**Post type:** image, the hero chart: `report/figures/hero_history.png`. The sub's rules require `[OC]` in the title and a top-level comment with the source and tools within an hour.
**When:** a weekday morning, US time, a day or two after Hacker News.

**Title:**
> [OC] Weekly new Stack Overflow questions, 2008–2026, vs what comparable Stack Exchange sites predict

**Required comment:**
> **Source:** Stack Exchange data dump, 2026-Q3 release (cut-off 30 September 2026), CC BY-SA 4.0.
> **Tools:** Python (DuckDB, statsmodels, pysyncon, PyMC), matplotlib.
>
> The orange line is new Stack Overflow questions per week (log scale). The dashed line is a "synthetic control": a weighted blend of 15 non-programming Stack Exchange sites, with weights chosen so it tracks Stack Overflow from 2017 to November 2022; the grey band is its 95% interval. Since ChatGPT, Stack Overflow has averaged 72% below it, and the gap grew from −34% in 2023 to −92% in 2026.
>
> Caveat: the comparison sites fell too (about −31% against their own trends), so this is Stack Overflow's fall beyond similar sites. Coding assistants and Stack Overflow's own changes overlap with ChatGPT, so it isn't proof of a single cause.
>
> Full write-up and code: https://johnpospisil.github.io/stackoverflow-decline/

## r/programming

**Post type:** link to the article. r/programming removes low-effort and promotional posts; a careful analysis with code is usually fine, but read the rules first.

**Title:**
> What happened to Stack Overflow? A pre-registered analysis of the 2026 data dump

**Optional comment** (if discussion starts):
> Author here. The tag lookup lets you check your own stack: https://johnpospisil.github.io/stackoverflow-decline/app/. One surprise was that older, well-documented tags fell less than newer ones, not more. Code and pre-registration are on GitHub if you want to check the method.
