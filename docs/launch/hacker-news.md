# Hacker News

**Status:** draft. Nothing is posted without John.
**When:** a weekday, 8–10 am US Eastern. Post the link, then the first comment right away.
**Link:** https://johnpospisil.github.io/stackoverflow-decline/

## Title (pick one; HN allows 80 characters)

1. **Stack Overflow questions are 72% below what comparable sites predict** (recommended: plain, factual, the number is the story)
2. What happened to Stack Overflow? A pre-registered analysis of the data dump
3. Show HN: Look up how far your Stack Overflow tag fell after ChatGPT (only if posting the app as the link; "Show HN" needs something people can try)

Avoid "killed", "dead" or "ChatGPT destroyed": the analysis doesn't show a single cause, and HN readers will say so.

## First comment

> Author here. I wanted to know how much of Stack Overflow's fall since late 2022 is beyond the decline that was already under way, and whether it's specific to programming.
>
> Method, briefly: I used the public Stack Exchange data dump (2026-Q3, 27 sites) and built a "synthetic" Stack Overflow, a weighted blend of 15 non-programming Stack Exchange sites (Physics, Math, Sci-Fi, Biology, Bicycles…) that tracked Stack Overflow closely from 2017 to Nov 2022. After ChatGPT, Stack Overflow's monthly questions averaged 72% below that blend (95% interval −76% to −68%). The gap grew every year: −34% in 2023, −92% in 2026. That's about 1.6 million fewer questions than expected (3.1 million if you count questions that were later deleted). Interrupted time series, ETS and Prophet forecasts all land at −81% to −83%.
>
> Things I think are interesting beyond the headline:
> - Every one of the 297 largest tags fell, but older, well-documented tags fell *less*, not more. That goes against the "thin training data" idea. Tags created after ChatGPT's training cut-off did hold up better.
> - The share of new askers who post again within a year fell from 44% to 29%. Questions answered within 24 hours fell from 67% to 55%.
> - The non-programming comparison sites also fell (−31% against their own trends). So the 72% is Stack Overflow's fall *beyond* similar sites, not its total loss to AI.
>
> I wrote down the hypotheses and decision rules before fitting any model on post-ChatGPT data. Four of the five pre-registered hypotheses (about tags, question mix, newcomers and answerers) are not supported after the planned multiple-comparison correction. The article says which choices I made after seeing results.
>
> What it doesn't show: that ChatGPT alone did this. Copilot, other assistants and Stack Overflow's own changes (Staging Ground, opinion questions) all overlap.
>
> Code (runs end to end from the raw dump, or on a synthetic sample in 4 minutes), pre-registration and data: https://github.com/johnpospisil/stackoverflow-decline. There's also a tag lookup: https://johnpospisil.github.io/stackoverflow-decline/app/
>
> Prior work: del Rio-Chanona, Laurentsyeva & Wachs (PNAS Nexus, 2024) found a 25% relative drop within six months; this extends the window to almost four years and adds tag, question and user detail. Happy to answer questions.
