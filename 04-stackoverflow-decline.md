# Project 4: What Happened to Stack Overflow?

**Working title:** *The Quiet Commons: How Generative AI Changed Who Asks, What Gets Asked and Who Answers on Stack Overflow*

**One-sentence pitch:** Use the full Stack Exchange post history to measure how much question activity fell after ChatGPT's release (November 30, 2022), which technologies and question types fell most, and what happened to the people who used to answer, using other Stack Exchange sites as a comparison group.

---

## 1. The question

**Primary:** How much of the drop in new Stack Overflow questions since late 2022 is beyond the pre-existing downward trend, and how does it vary by technology tag?

**Secondary:**
- **What** disappeared: easy/duplicate-style questions (which LLMs answer well) or hard ones? Track question length, code-block presence, score, close rate, duplicate rate and time-to-first-answer.
- **Who** disappeared: new users vs established users? Do newcomers stop arriving (a pipeline problem for the community)?
- **Answerers:** did the expert core shrink, keep answering fewer questions, or shift to the questions that remain?
- **Which tags held up?** Hypothesis: niche, new or fast-changing technologies (where LLM training data is thin) decline less than mature, well-documented ones (e.g. basic Python/JavaScript/SQL).

**A finding that would be wrong if:** the post-2022 decline is explained by the pre-2022 trend alone, or if non-programming Stack Exchange sites fall just as much (which would point to a platform-wide cause rather than AI coding tools).

## 2. Why now

- Stack Overflow is the clearest real-world case of generative AI replacing a public knowledge commons, which is a question about the future of open knowledge that matters well beyond programmers.
- Research to build on: del Rio-Chanona, Laurentsyeva & Wachs, *Are Large Language Models a Threat to Digital Public Goods? Evidence from Activity on Stack Overflow* (PNAS Nexus, 2024), found a large relative drop in posting after ChatGPT compared with platforms where ChatGPT was less accessible. Your contribution: **a longer post-period (2023–2026 instead of months), tag-level and user-cohort detail, question-quality outcomes, and a public dashboard.**
- Developers are your audience and they love this topic. It's close to guaranteed attention on Hacker News if the analysis is solid.

## 3. Data sources

| Source | What it gives you | Grain | Where |
|---|---|---|---|
| **Stack Exchange Data Dump** | Every post, comment, vote, user, badge and post history for every SE site (CC BY-SA) | post / user / vote, 2008–present | Stack Exchange now distributes it via a download link in your user profile settings (requires an account). Check current terms; older dumps are on the Internet Archive |
| **Stack Exchange Data Explorer (SEDE)** | SQL interface to recent data, refreshed roughly weekly | query results | data.stackexchange.com. Good for prototyping and for the most recent months |
| **Stack Exchange API** | Recent posts and tags for topping up past the latest dump | post | api.stackexchange.com |
| **Other SE sites (same dump)** | Comparison group: Mathematics, Super User, Server Fault, Unix & Linux, English Language, Cooking, etc. | post | same dump |
| **GH Archive** | Public GitHub event activity (issues, PRs) by repo/language: did help-seeking move to GitHub Discussions/Issues? | event × hour | gharchive.org (also on BigQuery) |
| **Stack Overflow Developer Survey** | Self-reported AI tool use by year (2023 onwards asks about AI) | respondent × year | survey.stackoverflow.co (ODbL) |
| **Google Trends** | Search interest for "stack overflow" vs "chatgpt" (context only) | week | trends.google.com |
| **Release dates** | ChatGPT (2022-11-30), GPT-4 (2023-03-14), GitHub Copilot GA (2022-06-21), Copilot Chat, SO's AI-answer ban (Dec 2022), moderator strike (June 2023), OpenAI–SO partnership (May 2024) | event | Hand-curated, cited table |

**Licensing note:** the data dump is CC BY-SA. If you redistribute derived datasets, keep the same license and attribution. Don't republish full post text unnecessarily; derived metrics are enough.

**Expected size:** the Stack Overflow Posts XML is ~100 GB uncompressed. Stream-parse it (`lxml.iterparse`) into Parquet with only the columns you need. Afterwards DuckDB handles everything on a laptop.

## 4. Building the dataset

1. **Ingest:** stream-convert Posts, Users, Votes, Comments and PostHistory XML for Stack Overflow plus ~10 comparison sites into Parquet. Keep the dump date in `DATA.md`.
2. **Question features:** creation week, tags, body length, number of code blocks, has-accepted-answer, score, view count, closed/duplicate status (from PostHistory), time to first answer, asker's account age and reputation at time of asking.
3. **User cohorts:** first-post month for each user; active-user definitions (asked/answered ≥ 1 in month); "core answerers" = top 1% of answer volume in 2019–2021.
4. **Tag taxonomy:** map the top ~300 tags into families (languages, frameworks, cloud, data/ML, DevOps) and add a **tag-age** feature (first appearance date). New tags are a proxy for "thin LLM training data".
5. **Weekly panels:** site × week and tag × week counts of questions, answers, new users and active answerers.
6. **Checks:** monthly totals compared with SEDE for overlap months, deleted-post handling documented (the dump excludes deleted posts, so declines may be slightly understated), no duplicate post IDs.

## 5. Method

### Headline effect
- **Interrupted time series** on weekly new questions (log), with pre-period trend and seasonality (holidays, the academic calendar), break at 2022-11-30. Report level and slope change with intervals.
- **Synthetic control / comparative ITS:** build a weighted combination of non-programming SE sites that tracks Stack Overflow's pre-2022 trajectory, then measure the post-2022 gap. Use `pysyncon` or a simple augmented synthetic control; show placebo runs on each donor site.
- **Forecast counterfactual:** fit a model (Prophet or ETS) on pre-2022 data and plot what activity "would have been". Easy for readers to understand; label it clearly as a counterfactual.

### Heterogeneity
- **Tag-level difference-in-differences:** decline vs tag characteristics (age, size, documentation maturity, LLM-friendliness). Partial pooling via a hierarchical model so small tags don't produce noisy extremes.
- **Question-mix shift:** did the share of "beginner-like" questions (short, low-rep askers, high duplicate rate) fall? Compare post-period distributions with the pre-period.
- **User cohorts:** survival curves for monthly new-user cohorts (do 2023 newcomers come back less often?) and retention of core answerers.

### Robustness
- Separate out other shocks: Stack Overflow's own policy changes, the June 2023 moderator strike, and the long pre-2022 decline. Show estimates with and without each period.
- Alternative break dates: GPT-4 (March 2023) and Copilot GA (June 2022) as secondary breaks.
- Deleted-post bias: compare dump counts with SEDE where possible.

## 6. Charts

| # | Chart | Purpose |
|---|---|---|
| **Hero** | **Weekly new questions, 2008–today**, actual vs synthetic-control counterfactual, with labelled annotations (ChatGPT, GPT-4, strike, OpenAI deal) | The chart that goes viral; must be impeccable |
| 2 | **Tag decline ranking:** dot plot of % change vs counterfactual for the top 50 tags, coloured by tag family, with intervals | "Which technologies fell most" |
| 3 | Scatter: tag decline vs tag age (or size), with fitted line and labelled outliers | Tests the "thin training data" hypothesis |
| 4 | Cohort retention heatmap: new-user cohort month × months since first post | Shows the newcomer pipeline problem |
| 5 | Slope chart: share of questions from new users, closed-as-duplicate rate and median question length, 2021 vs latest year | What *kind* of questions remain |
| 6 | Small multiples: comparison SE sites indexed to 2019 = 100 | Shows the effect is specific to programming |
| 7 | Time-to-first-answer and % answered over time (line with band) | Is the remaining community still responsive? |

**Interactive:** a "tag lookup" page where readers enter their tag (e.g. `rust`, `pandas`, `react`) and see its trajectory and counterfactual. Developers will search for their own stack and share the result.

## 7. Repo skeleton

```
stackoverflow-decline/
  README.md
  DATA.md                  # dump date, license, deleted-post caveat, event table sources
  Makefile
  pyproject.toml, uv.lock
  src/sod/
    ingest/xml_to_parquet.py, sede.py, gharchive.py, survey.py
    build/question_features.py, cohorts.py, tag_taxonomy.py, panels.py
    models/its.py, synth_control.py, tag_did.py, cohort_survival.py
    viz/theme.py, figures.py
  data/reference/events.csv, tag_families.csv
  tests/                   # parser on fixture XML, totals vs SEDE, pinned headline estimates
  notebooks/
  report/index.qmd
  app/
```

## 8. Milestones

| Week | Deliverable |
|---|---|
| 1 | Download dump; streaming XML → Parquet for SO + comparison sites; parser tests on fixtures |
| 2 | Question features, user cohorts, tag taxonomy; reconcile with SEDE |
| 3 | ITS + synthetic control; hero chart v1 with placebo tests |
| 4 | Tag heterogeneity + question-mix analysis |
| 5 | User cohorts and answerer retention; GH Archive side analysis (optional) |
| 6 | Article + tag lookup app |
| 7 | Review by a long-time SO user and a statistician friend; publish |

## 9. Distribution
- **Hacker News is the main target**: post on a weekday morning (US time) with a plain title ("Stack Overflow questions are down X% vs what the trend predicted; here's which tags fell most").
- r/programming, r/dataisbeautiful (hero chart), LinkedIn, Bluesky dev community.
- Stack Overflow's own Meta site: the community there takes careful analysis seriously, and their feedback will strengthen the work.
- Publish the weekly site × tag panel on Kaggle / Hugging Face (CC BY-SA) for others to reuse.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Already studied (PNAS Nexus paper) | Cite it prominently; your angle is longer horizon + tags + cohorts + quality + open tool |
| Pre-existing decline confounds the effect | ITS with trend, synthetic control, placebo dates |
| Dump excludes deleted posts | Document; compare with SEDE; note the likely direction of bias |
| Large XML files | Streaming parser, column pruning, Parquet; process one table at a time |
| Comparison sites are also affected by AI | Present as "programming-specific excess decline"; show sites by how AI-exposed they are |

## 11. Stretch goals
- Use embeddings (or a small classifier) to label question "difficulty" and test whether the remaining questions are harder.
- Extend to other knowledge commons: Wikipedia edit activity, Reddit programming subreddits (if data access allows).
- ~~Make it a living tracker with a monthly refresh from SEDE / the API.~~ Dropped 2026-10-22: the project is a fixed snapshot of the 2026-Q3 dump.
