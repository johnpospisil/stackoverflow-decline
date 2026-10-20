# DATA

Sources, licences, retrieval details and known gaps for every dataset used in this project.

## 1. Stack Exchange Data Dump (primary source)

| Field | Value |
|---|---|
| Release | 2026-Q3 quarterly dump ("Global data dump", all Stack Exchange sites) |
| Uploaded by Stack Exchange | 2026-10-06 |
| Data cut-off | 2026-09-30. Last SO post: `2026-09-30T08:36:56` (UTC) from the tail of `Posts.xml`. Treat 2026-09-30 as a partial day |
| Downloaded | 2026-10-19 |
| Download size | 91.9 GB (Global dump, 364 site archives) |
| Access | stackoverflow.com → profile → Settings → Access → **Data dump access** (login required) |
| Raw location (not in git) | `/Volumes/Drive3/data/` (external HFS+ USB drive) |
| Format | One `.7z` per site, each containing XML tables |

### Access terms (verbatim, as accepted on 2026-10-19)

Page text:

> You can access this site's data for personal use. For inquiries about using the data for large language model (LLM) training, please contact us.

Checkbox you must tick before downloading:

> I understand that this file is being provided to me for my own use and for projects that do not include training a large language model (LLM), and that should I distribute this file for the purpose of LLM training, Stack Overflow reserves the right to decline to allow me access to future downloads of this data dump.

This project is a statistical analysis and does not train an LLM.
Re-check this wording before publishing any derived dataset (see section 5).

### Licence

The dump ships with `license.txt`. Every site's copy is identical; a copy is saved in [docs/data-dump-license.txt](docs/data-dump-license.txt). Key points:

- Content is CC BY-SA (2.5, 3.0 or 4.0, depending on when it was posted). The dump as a whole is CC BY-SA 4.0 for non-beta sites.
- If content is republished, the licence requires links to the original post and to each author's profile.
- **Project rule:** publish derived metrics only (counts, rates, lengths). Do not republish post bodies, titles or user names. Derived panels are released under CC BY-SA 4.0 with attribution to Stack Exchange.

### Schema

The official schema doc ships inside each archive and is copied to [docs/sede-and-data-dump-schema.md](docs/sede-and-data-dump-schema.md) (version dated 2025-09-30, from https://meta.stackexchange.com/a/2678). Points that affect parsing:

- Nullable columns are **omitted** from the `<row>` element when NULL, not written as empty values.
- `Body` is rendered HTML, not Markdown. Find code blocks with `<pre><code>`.
- `Posts` excludes deleted posts. The `PostsWithDeleted` table exists only in SEDE.
- `PostTypeId`: 1 = question, 2 = answer. Other types (wikis, articles, collectives) must be filtered out.

### Files per site

Each site folder contains:
`Badges.xml`, `Comments.xml`, `PostHistory.xml`, `PostLinks.xml`, `Posts.xml`, `Tags.xml`, `Users.xml`, `Votes.xml`, `license.txt`, `sede-and-data-dump-schema.md`.

### Sites kept (27 of 364)

The other 337 archives (all `*.meta.*` sites except Meta Stack Overflow, plus unrelated main sites) were deleted on 2026-10-19. They can be downloaded again from each site's own Data dump access page.

| Site | Group | Why it's included | `.7z` | Extracted | `Posts.xml` |
|---|---|---|---|---|---|
| stackoverflow.com | **Treatment** | Subject of the study | 68.9 GB | 334 GB | 105.6 GB |
| meta.stackoverflow.com | Context | Policy changes, Dec 2022 AI-answer ban, June 2023 moderator strike | 0.38 GB | 2.3 GB | 0.22 GB |
| ru.stackoverflow.com | SO in another language | ChatGPT was not officially available in Russia, so lower exposure (same idea as del Rio-Chanona et al., 2024) | 1.11 GB | 6.5 GB | 2.03 GB |
| es.stackoverflow.com | SO in another language | Spanish-language programming Q&A | 0.55 GB | 3.2 GB | 1.06 GB |
| pt.stackoverflow.com | SO in another language | Portuguese-language programming Q&A | 0.47 GB | 2.6 GB | 0.79 GB |
| ja.stackoverflow.com | SO in another language | Japanese-language programming Q&A | 0.08 GB | 0.49 GB | 0.16 GB |
| superuser.com | Tech, also exposed to AI | Computer help; LLMs answer these too | 1.41 GB | 6.6 GB | 1.72 GB |
| serverfault.com | Tech, also exposed to AI | Sysadmin | 0.91 GB | 4.2 GB | 1.24 GB |
| askubuntu.com | Tech, also exposed to AI | Linux help | 1.15 GB | 6.0 GB | 1.46 GB |
| unix.stackexchange.com | Tech, also exposed to AI | Shell and Unix | 0.76 GB | 3.8 GB | 1.03 GB |
| softwareengineering.stackexchange.com | Tech, also exposed to AI | Design and conceptual questions | 0.38 GB | 1.8 GB | 0.44 GB |
| dba.stackexchange.com | Tech, also exposed to AI | Databases and SQL | 0.34 GB | 1.7 GB | 0.49 GB |
| math.stackexchange.com | Comparison pool (caution) | Large and active, but LLMs answer math too. Run models with and without it | 3.93 GB | 19 GB | 6.32 GB |
| physics.stackexchange.com | Comparison pool | Science | 0.81 GB | 3.9 GB | 1.13 GB |
| chemistry.stackexchange.com | Comparison pool | Science | 0.14 GB | 0.70 GB | 0.18 GB |
| biology.stackexchange.com | Comparison pool | Science | 0.09 GB | 0.43 GB | 0.11 GB |
| english.stackexchange.com | Comparison pool | Language (some AI exposure) | 0.48 GB | 2.3 GB | 0.57 GB |
| philosophy.stackexchange.com | Comparison pool | Humanities | 0.17 GB | 0.79 GB | 0.21 GB |
| history.stackexchange.com | Comparison pool | Humanities | 0.10 GB | 0.54 GB | 0.11 GB |
| cooking.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.10 GB | 0.44 GB | 0.11 GB |
| diy.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.27 GB | 1.2 GB | 0.32 GB |
| travel.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.17 GB | 0.83 GB | 0.18 GB |
| bicycles.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.09 GB | 0.40 GB | 0.10 GB |
| gaming.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.26 GB | 1.2 GB | 0.30 GB |
| scifi.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.36 GB | 1.7 GB | 0.39 GB |
| movies.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.10 GB | 0.51 GB | 0.11 GB |
| rpg.stackexchange.com | Comparison pool | Hobby, low AI exposure | 0.30 GB | 1.5 GB | 0.36 GB |

Sizes: `.7z` in GB (10^9 bytes); extracted size from `du -sh` (GiB); `Posts.xml` in GB.

Stack Overflow table sizes (GB): PostHistory 185.0, Posts 105.6, Comments 28.2, Votes 24.1, Users 8.2, Badges 6.5, PostLinks 0.8, Tags 0.006.

Extraction finished 2026-10-19 (macOS Archive Utility). Every XML file in all 27 sites ends with its closing root tag, so no file was cut off mid-extraction.

## 2. Known gaps and caveats

- **Deleted posts are missing.** The dump excludes deleted posts and many deleted users. If deletion rates changed after 2022, declines may be slightly understated. Compare against SEDE where possible.
- **Possible watermarking or data poisoning.** Community reports say Stack Exchange began watermarking or poisoning dumps starting with the 2025-06-30 release. **TODO:** check this dump against the official checksums and the community list of affected dumps, and record the result here. Count-based metrics should be less exposed than text features (body length, code blocks), but check both against SEDE.
- **Last quarter may be incomplete.** Posts from the final days before the cut-off may not yet have answers, votes or closures. Trim the panel or flag the last 4–8 weeks for outcomes that take time to arrive (time to first answer, close rate).
- **Removed users.** `OwnerUserId` is missing for posts whose author was deleted, which affects user-cohort analysis.

## 3. Reconciliation checks (to do)

- [ ] Monthly question counts for SO compared with SEDE for overlapping months
- [ ] No duplicate `Post.Id` values
- [x] Max `CreationDate` matches the stated cut-off (SO 2026-09-30, Math 2026-09-30; small sites end earlier because they post less often)
- [x] All XML files complete (closing root tag present)
- [ ] Watermarking check (see section 2)

## 4. Other sources (not yet retrieved)

| Source | URL | Licence | Retrieved |
|---|---|---|---|
| Stack Exchange Data Explorer (SEDE) | https://data.stackexchange.com | CC BY-SA | — |
| Stack Exchange API (data after the dump cut-off) | https://api.stackexchange.com | CC BY-SA | — |
| Stack Overflow Developer Survey | https://survey.stackoverflow.co | ODbL | — |
| GH Archive (optional) | https://www.gharchive.org | — | — |
| Event dates (`data/reference/events.csv`) | Hand-curated, cited per row | — | — |

## 5. Before publishing

- [ ] Re-read the Data dump access terms. Note any change since 2026-10-19.
- [ ] Confirm published datasets contain derived metrics only (no post text or user names).
- [ ] Include CC BY-SA 4.0 attribution to Stack Exchange on every published dataset and chart.
