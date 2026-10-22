# LinkedIn and Bluesky

**Status:** drafts. Nothing is posted without John.
**When:** LinkedIn on a weekday morning; Bluesky the same day as Hacker News. Attach the social chart, hero B (`report/figures/hero_gap.png`), on both.

## LinkedIn (one post)

> How much has Stack Overflow really fallen since ChatGPT, beyond the decline that was already happening?
>
> I analysed the public Stack Exchange data dump (27 sites, to September 2026). I compared Stack Overflow with a "synthetic" version built from 15 non-programming Stack Exchange sites that tracked it closely before ChatGPT. Since then, Stack Overflow's new questions have averaged 72% below that comparison. The gap grew every year, from −34% in 2023 to −92% in 2026: about 1.6 million fewer questions than expected.
>
> Three things stood out:
> • Every one of the 297 largest tags fell, but older, well-documented technologies fell less, not more.
> • Fewer newcomers come back: 44% used to post again within a year, now 29%.
> • Fewer questions get a quick answer: 67% were answered within a day, now 55%.
>
> I wrote down the hypotheses before running any model on post-ChatGPT data, and the article reports the ones that didn't hold up. Four of five weren't supported after correcting for multiple tests.
>
> Article, code and a tag lookup (try your own stack): https://johnpospisil.github.io/stackoverflow-decline/
>
> #DataScience #CausalInference #StackOverflow #AI

## Bluesky thread (each post 300 characters or fewer; `tests/test_launch.py` checks)

1/ Since ChatGPT, new Stack Overflow questions have averaged 72% below what comparable Stack Exchange sites predict. The gap grew every year: −34% in 2023, −92% in 2026. About 1.6 million fewer questions than expected. 🧵

2/ How: a "synthetic" Stack Overflow, a weighted blend of 15 non-programming Stack Exchange sites that tracked it closely from 2017 to Nov 2022. Three other methods (time series, two forecasts) land at −81% to −83%. Stack Overflow's gap is the largest of all 16 sites.

3/ Every one of the 297 largest tags fell. But older, well-documented tags fell less, not more, which goes against the "chatbots answer what they've seen most" story. Tags newer than ChatGPT's training data did hold up better.

4/ Who left? The share of new askers who post again within a year fell from 44% to 29%. Questions answered within 24 hours fell from 67% to 55%. The questions still asked are longer.

5/ Caveats: the comparison sites fell too (−31% vs their own trends), so 72% is the fall beyond them. Copilot and Stack Overflow's own changes overlap with ChatGPT. Hypotheses were pre-registered; none of the 4 secondary ones survived the correction for multiple tests.

6/ Article, code, pre-registration and a tag lookup to check your own stack: https://johnpospisil.github.io/stackoverflow-decline/

## X thread (each post 280 characters or fewer; `tests/test_launch.py` checks)

**When:** the same day as Hacker News. Attach hero A (`report/figures/hero_history.png`) to post 1 and hero B (`report/figures/hero_gap.png`) to post 2. The link goes in the last post: X shows posts with links less widely.

X1/ Since ChatGPT, new Stack Overflow questions have averaged 72% below what comparable Stack Exchange sites predict. The gap grew every year: −34% in 2023, −92% in 2026. 🧵

X2/ That's about 1.6 million fewer questions than expected, from Dec 2022 to Sep 2026. The comparison is a "synthetic" Stack Overflow built from 15 non-programming Stack Exchange sites that tracked it closely before ChatGPT.

X3/ Every one of the 297 largest tags fell. Surprise: older, well-documented tags fell less, not more. Tags newer than ChatGPT's training data held up better.

X4/ The community that's left is smaller and slower. New askers who post again within a year: 44% → 29%. Questions answered within a day: 67% → 55%.

X5/ Caveats: the comparison sites fell too, so 72% is the fall beyond them. Copilot and Stack Overflow's own changes overlap with ChatGPT. I pre-registered the hypotheses; the 4 secondary ones didn't survive correction.

X6/ Article, code and a lookup to check your own tag: https://johnpospisil.github.io/stackoverflow-decline/
