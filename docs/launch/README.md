# Launch kit

Drafts for the launch. **Nothing is posted, uploaded or made public without John.**

| File | What |
|---|---|
| [hacker-news.md](hacker-news.md) | Title options and the author's first comment |
| [meta-stack-overflow.md](meta-stack-overflow.md) | Discussion post for meta.stackoverflow.com |
| [reddit.md](reddit.md) | r/dataisbeautiful (hero chart, [OC]) and r/programming |
| [linkedin-bluesky.md](linkedin-bluesky.md) | LinkedIn post, a 6-post Bluesky thread and a 6-post X thread |
| [reviewer-questions.md](reviewer-questions.md) | 15 likely questions with short answers |

## Checklist, in order

**Before launch day**
1. Open stackoverflow.com → Settings → Data dump access and check the terms still match the wording in [DATA.md](../../DATA.md). If they changed, stop and reassess what can be published.
2. Check https://meta.stackexchange.com/a/402072 for official 2026-09-30 checksums and compare them with `data/reference/dump_checksums.csv`.
3. Read the article and the drafts once more, in a browser.

**Launch day**
4. Make the GitHub repository public: Settings → General → Danger Zone → Change visibility.
5. Turn on Pages: Settings → Pages → Source: **GitHub Actions**. Then rerun the `pages` workflow (Actions → pages → Run workflow). Check https://johnpospisil.github.io/stackoverflow-decline/ and `/app/`.
6. Upload the dataset to Hugging Face: create a dataset repo `johnpospisil/stackoverflow-decline-panels-2026q3` and upload the folder `/Volumes/Drive3/sod/release/stackoverflow-decline-panels-2026q3/` (Drive3 must be mounted). Then add its link to the README's "Dataset" row.
7. Post to Hacker News (weekday, 8–10 am US Eastern), then add the first comment.
8. Same day: Bluesky and X threads, and LinkedIn. Next day or two: Meta Stack Overflow, then Reddit (not the same day as each other).
9. Answer comments for the first day or two; [reviewer-questions.md](reviewer-questions.md) has the short answers.
