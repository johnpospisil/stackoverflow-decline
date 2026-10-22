# What happened to Stack Overflow?

**Since ChatGPT, new Stack Overflow questions have averaged 72% below what comparable Stack Exchange sites predict**: about 1.6 million fewer questions from December 2022 to September 2026. This repository has the full analysis of the public Stack Exchange data dump (2026-Q3, 27 sites), pre-registered before any model saw post-ChatGPT data.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="report/figures/hero_history_dark.png">
  <img alt="Weekly new Stack Overflow questions, 2008 to 2026, on a log scale. After a slow decline from 2014, questions fall steeply after ChatGPT, to a few hundred a week by 2026, far below a dashed synthetic-control line built from non-programming Stack Exchange sites." src="report/figures/hero_history.png">
</picture>

## Findings

- **The gap is large and grew every year:** −34% in 2023, −92% in 2026, against a "synthetic" Stack Overflow built from 15 non-programming sites. Over the whole period it averaged **−72%** (95% interval −76% to −68%). Stack Overflow's gap is the largest of all 16 sites, and three other methods agree (−81% to −83%). Every one of 15 pre-registered robustness checks stays between −60% and −74%.
- **Every large tag fell, but not the way the "thin training data" theory predicts.** All 297 of the largest tags fell against their own trends. Older, well-documented tags fell *less*, not more: clearly in the main model, and only weakly in plain counts. Exact tag rankings depend on the model's trend assumption. Tags created after ChatGPT's training cut-off held up better (−49% against a lifecycle benchmark, vs −85% for the median large tag).
- **The community that remains is smaller and slower.** The share of newcomers who post again within a year fell from 44% to 29%. Answers within 24 hours fell from 67% to 55% of questions. The questions still asked are longer.

**What this doesn't show:** that ChatGPT alone caused the fall. Coding assistants and Stack Overflow's own changes coincide with it. The comparison sites fell too (−31% against their own trends), so −72% is Stack Overflow's fall *beyond* similar sites, and its total loss to AI is probably larger.

## Read more

| | |
|---|---|
| **Article** | [johnpospisil.github.io/stackoverflow-decline](https://johnpospisil.github.io/stackoverflow-decline/): the full write-up, with methods, robustness and limits. Source: [report/index.qmd](report/index.qmd). |
| **Tag lookup** | [johnpospisil.github.io/stackoverflow-decline/app](https://johnpospisil.github.io/stackoverflow-decline/app/): type a tag (python, rust, reactjs…) to see its trajectory, its expected line and its rank. Source: [app/](app/). |
| **Dataset** | [huggingface.co/datasets/audiofreak7/stackoverflow-decline-panels-2026q3](https://huggingface.co/datasets/audiofreak7/stackoverflow-decline-panels-2026q3): weekly and monthly site and tag panels (CC BY-SA 4.0), built with `make release`. Data card: [docs/dataset-card.md](docs/dataset-card.md). |
| **Pre-registration** | [PREREGISTRATION.md](PREREGISTRATION.md): hypotheses and decision rules locked at tag `prereg-v1`, with every later change logged and dated. |
| **Validation** | [report/validation.md](report/validation.md): an independent-reviewer pass, listing the issues found and how each was handled. |
| **Data sources** | [DATA.md](DATA.md): dump version, checksums, licence, access terms and known gaps. |

Pre-registered scorecard: **H1** (questions fell beyond trend and comparison sites) supported. **H2–H5** (tags, question mix, newcomers, answerers) not supported after the pre-registered correction for multiple tests. Details are in the article.

## Reproduce

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). [Quarto](https://quarto.org) is needed only for the article.

```bash
uv sync
make all SAMPLE=1   # whole pipeline on a small synthetic dump, about 4 minutes (what CI runs)
make test
```

For the real analysis, download the Stack Exchange data dump (2026-Q3; stackoverflow.com → Settings → Data dump access) and extract the 27 sites listed in [DATA.md](DATA.md). Then point the pipeline at it:

```bash
export SOD_RAW_DIR=/path/to/dump   # one folder per site, XML files inside
export SOD_DATA_DIR=/path/to/work  # about 10 GB of Parquet
make all                           # about 2.5 hours on a laptop
```

Seeds are fixed, so reruns give identical results. `tests/test_pinned_estimates.py` checks every headline number.

## Licence and attribution

Code: MIT ([LICENSE](LICENSE)). Data and derived panels: **CC BY-SA 4.0**, from the Stack Exchange data dump, contributed by Stack Exchange users. This project publishes derived counts only, no post text or user names. It is an independent analysis, not affiliated with or endorsed by Stack Overflow or Stack Exchange. It does not train language models, in line with the dump's access terms.

Related work: del Rio-Chanona, Laurentsyeva & Wachs (2024), [Large language models reduce public knowledge sharing on online Q&A platforms](https://doi.org/10.1093/pnasnexus/pgae400), *PNAS Nexus* 3(9).

By John Pospisil.
