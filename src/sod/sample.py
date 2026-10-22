"""P28: a small synthetic Stack Exchange dump for the fast pipeline path (make all SAMPLE=1).

Writes all 8 XML tables for all 27 sites into SOD_RAW_DIR, in the dump's format, plus a copy
of data/reference into SOD_REFERENCE_DIR. No real post text, user or count is used: monthly
question volumes follow a made-up common trend, Stack Overflow and the other programming sites
get a growing post-2022-11 drop, and users, answers, closures, votes and comments are drawn at
random. Stack Overflow questions use the real top-300 tag names (from tag_families.csv) plus a
few made-up post-2021 tags, so the tag models have the same shape as the real run.

The numbers it produces mean nothing; the point is that every stage runs end to end in a few
minutes (CI). Deterministic for a given seed.

Usage: python -m sod.sample [--scale 1.0] [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import shutil
import warnings
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from sod import config

warnings.filterwarnings("ignore", message="The 'generic' unit for NumPy timedelta")
REAL_REFERENCE = config.REPO_ROOT / "data" / "reference"
START = pd.Timestamp("2008-08-01")
END = pd.Timestamp(config.DUMP_CUTOFF) + pd.Timedelta(days=1)  # exclusive
BREAK = pd.Timestamp(config.BREAK_DATE)
NEW_TAGS = [f"sample-newtech-{i}" for i in range(1, 9)]
# Stack Overflow questions per month at the 2019 level (scale 1); other sites get less.
SO_2019 = 1500
EFFECT = {"treated": 1.0, "so_language": 0.8, "tech_exposed": 0.6, "donor": 0.0, "context": 0.3}


def _attrs(d: dict) -> str:
    return " ".join(f'{k}="{escape(str(v), quote=True)}"' for k, v in d.items() if v is not None)


def _ts(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}"


class Writer:
    """Streams one XML table."""

    def __init__(self, path: Path, root: str):
        self.f = path.open("w", encoding="utf-8")
        self.f.write(f'﻿<?xml version="1.0" encoding="utf-8"?>\n<{root}>\n')
        self.root = root

    def row(self, **kw) -> None:
        self.f.write(f"  <row {_attrs(kw)} />\n")

    def close(self) -> None:
        self.f.write(f"</{self.root}>\n")
        self.f.close()


def monthly_rate(months: pd.DatetimeIndex, group: str, rng, level: float, start) -> np.ndarray:
    """Expected questions per month: growth to 2013, slow decline, COVID bump, then the
    group's post-ChatGPT drop (log-linear in months since the break)."""
    yrs = (months - pd.Timestamp("2013-01-01")).days / 365.25
    growth = np.where(yrs < 0, np.exp(0.9 * yrs), 1.0)
    trend = np.exp(rng.normal(-0.06, 0.03) * np.clip(yrs, 0, None))
    covid = np.where((months >= "2020-04-01") & (months < "2020-10-01"), 1.12, 1.0)
    common_post = np.exp(-0.004 * np.clip((months - BREAK).days / 30.44, 0, None))
    m_post = np.clip((months - BREAK).days / 30.44, 0, None)
    drop = np.exp(-0.06 * EFFECT[group] * m_post)
    season = 1 + 0.06 * np.cos(2 * np.pi * (months.month - 3) / 12)
    noise = np.exp(rng.normal(0, 0.05, len(months)))
    rate = level * growth * trend * covid * common_post * drop * season * noise
    return np.where(months >= start, rate, 0.0)


def random_times(month: pd.Timestamp, n: int, rng) -> pd.DatetimeIndex:
    """n timestamps in the month, fewer at weekends."""
    days = pd.date_range(month, month + pd.offsets.MonthEnd(0), freq="D")
    w = np.where(days.dayofweek >= 5, 0.6, 1.0)
    d = rng.choice(len(days), size=n, p=w / w.sum())
    secs = rng.integers(0, 86400, n) + rng.integers(0, 1000, n) / 1000
    out = days[d] + pd.to_timedelta(secs, unit="s")
    return out[out < END]


def body(chars: int, code_blocks: int) -> str:
    text = "<p>" + ("lorem ipsum " * (chars // 12 + 1))[:chars] + "</p>"
    for _ in range(code_blocks):
        text += "\n<pre><code>x = f(y)\nprint(x)\n</code></pre>"
    return text


def site_tags(site: str, rng) -> tuple[list[str], np.ndarray, list[pd.Timestamp]]:
    """Tag vocabulary, weights and first-use dates for a site."""
    if site == config.TREATED:
        fam = pd.read_csv(REAL_REFERENCE / "tag_families.csv")
        names = fam["tag"].tolist()
        w = 1 / (fam["rank_2019_2021"].to_numpy() + 8) ** 0.9
        starts = [
            START + pd.Timedelta(days=int(d))
            for d in rng.choice(np.r_[np.zeros(5), rng.uniform(0, 3650, 50)], len(names))
        ]
        # a few mid-life tags (first used 2014-2018) for the lifecycle benchmark
        for i in rng.choice(np.arange(60, 300), 25, replace=False):
            starts[i] = pd.Timestamp("2014-01-01") + pd.Timedelta(days=int(rng.uniform(0, 1800)))
        names += NEW_TAGS
        w = np.r_[w, np.full(len(NEW_TAGS), w[15])]
        starts += [
            pd.Timestamp("2021-11-01") + pd.Timedelta(days=int(d))
            for d in rng.uniform(0, 400, len(NEW_TAGS))
        ]
        return names, w, starts
    names = [f"topic-{i}" for i in range(1, 31)]
    return names, 1 / np.arange(1, 31) ** 0.8, [START] * 30


def make_site(site: str, out: Path, rng, scale: float) -> dict:
    group = config.site_group(site)
    is_so = site == config.TREATED
    level = SO_2019 * scale if is_so else rng.uniform(25, 90) * scale
    start = (
        START
        if is_so
        else pd.Timestamp("2010-07-01") + pd.Timedelta(days=int(rng.integers(0, 1200)))
    )
    months = pd.date_range(START, END - pd.Timedelta(days=1), freq="MS")
    lam = monthly_rate(months, group, rng, level, start)
    tags, tag_w, tag_start = site_tags(site, rng)
    tag_start = np.array(tag_start, dtype="datetime64[ns]")
    tag_effect = rng.normal(0, 0.012, len(tags))  # tag-specific post-break slope

    d = out / site
    d.mkdir(parents=True, exist_ok=True)
    W = {
        t: Writer(d / f"{t}.xml", r)
        for t, r in [
            ("Posts", "posts"),
            ("PostHistory", "posthistory"),
            ("Votes", "votes"),
            ("Comments", "comments"),
            ("PostLinks", "postlinks"),
        ]
    }
    users: dict[int, pd.Timestamp] = {}  # id -> creation date
    recent: list[int] = []
    answerers: list[tuple[int, pd.Timestamp, pd.Timestamp]] = []
    pid = ph = vid = cid = lid = 0
    tag_count: dict[str, int] = {}
    q_ids: list[int] = []
    next_user = 1

    def new_user(at: pd.Timestamp) -> int:
        nonlocal next_user
        uid = next_user
        next_user += 1
        lag = 0 if rng.random() < 0.6 else rng.exponential(200)
        users[uid] = at - pd.Timedelta(days=lag)
        return uid

    for m, mu in zip(months, lam, strict=True):
        n = rng.poisson(mu)
        if n == 0:
            continue
        post = m >= BREAK
        msince = max((m - BREAK).days / 30.44, 0)
        # answerer pool: new answerers join each month, each stays active for a while
        for _ in range(rng.poisson(max(mu / 40, 0.3)) + (not answerers)):
            life = rng.lognormal(3.2 if not post else 2.6, 0.8)
            answerers.append((new_user(m), m, m + pd.Timedelta(days=30.44 * life)))
        active = [a for a in answerers if a[1] <= m < a[2]] or answerers[-1:]
        aw = 1 / np.arange(1, len(active) + 1) ** 1.1
        aw /= aw.sum()
        times = random_times(m, n, rng).sort_values()
        avail = np.flatnonzero(tag_start <= np.datetime64(m))
        w = tag_w[avail] * np.exp(tag_effect[avail] * msince)
        w /= w.sum()
        p_new = 0.35 + (0.08 if post else 0)
        for t in times:
            pid += 1 + (rng.random() < (0.5 if post else 0.35))  # gaps = deleted posts
            if rng.random() < 0.02:  # a vote on a deleted post
                vid += 1
                W["Votes"].row(
                    Id=vid, PostId=pid - 1, VoteTypeId=2, CreationDate=_ts(t.normalize())
                )
            if rng.random() < p_new or not recent:
                uid = new_user(t)
            else:
                uid = recent[-1 - min(int(rng.exponential(len(recent) / 4)), len(recent) - 1)]
            recent.append(uid)
            if len(recent) > 3000:
                recent = recent[-2000:]
            k = rng.choice([1, 2, 3], p=[0.3, 0.45, 0.25])
            qt = [tags[i] for i in rng.choice(avail, size=min(k, len(avail)), replace=False, p=w)]
            for tg in qt:
                tag_count[tg] = tag_count.get(tg, 0) + 1
            tag_str = "|" + "|".join(qt) + "|"
            chars = int(rng.lognormal(6.6 + (0.3 if post and is_so else 0), 0.6))
            n_ans = rng.poisson(1.5 if not post else (0.9 if group != "donor" else 1.3))
            qid = pid
            ans = []
            for _ in range(n_ans):
                delay = rng.exponential(2.0) if rng.random() < 0.7 else rng.lognormal(4, 2)
                at = t + pd.Timedelta(hours=delay * (1.5 if post else 1))
                if at < END:
                    ans.append(at)
            closed = rng.random() < 0.08
            dup = closed and rng.random() < 0.6 and len(q_ids) > 10
            accepted = None
            ans_ids = []
            for at in sorted(ans):
                pid += 1
                ans_ids.append((pid, at))
            if ans_ids and rng.random() < 0.5:
                accepted = ans_ids[0][0]
            close_at = t + pd.Timedelta(hours=rng.exponential(10)) if closed else None
            if close_at is not None and close_at >= END:
                close_at, closed, dup = None, False, False
            W["Posts"].row(
                Id=qid,
                PostTypeId=1,
                AcceptedAnswerId=accepted,
                CreationDate=_ts(t),
                Score=int(rng.poisson(2 if not post else 0.6)) - int(rng.random() < 0.2),
                ViewCount=int(rng.lognormal(5, 1.2)),
                Body=body(chars, int(rng.poisson(1.2))),
                OwnerUserId=uid if rng.random() > 0.03 else None,
                OwnerDisplayName=None,
                LastActivityDate=_ts(t),
                Title="Sample question " + "word " * int(rng.integers(3, 12)),
                Tags=tag_str,
                AnswerCount=len(ans_ids),
                CommentCount=0,
                ClosedDate=_ts(close_at) if closed else None,
                ContentLicense="CC BY-SA 4.0",
            )
            ph += 1
            W["PostHistory"].row(
                Id=ph,
                PostHistoryTypeId=3,
                PostId=qid,
                CreationDate=_ts(t),
                UserId=uid,
                Text=tag_str,
            )
            if closed:
                ph += 1
                orig = [int(q_ids[int(rng.integers(0, len(q_ids)))])] if dup else []
                W["PostHistory"].row(
                    Id=ph,
                    PostHistoryTypeId=10,
                    PostId=qid,
                    CreationDate=_ts(close_at),
                    Comment=101 if dup else 102,
                    Text=json.dumps({"OriginalQuestionIds": orig, "Voters": [{"Id": 1}]}),
                )
                if dup:
                    lid += 1
                    W["PostLinks"].row(
                        Id=lid,
                        CreationDate=_ts(close_at),
                        PostId=qid,
                        RelatedPostId=orig[0],
                        LinkTypeId=3,
                    )
            q_ids.append(qid)
            for aid, at in ans_ids:
                who = active[rng.choice(len(active), p=aw)][0]
                W["Posts"].row(
                    Id=aid,
                    PostTypeId=2,
                    ParentId=qid,
                    CreationDate=_ts(at),
                    Score=int(rng.poisson(1.5)),
                    Body=body(int(rng.lognormal(6, 0.6)), int(rng.random() < 0.6)),
                    OwnerUserId=who,
                    LastActivityDate=_ts(at),
                    CommentCount=0,
                    ContentLicense="CC BY-SA 4.0",
                )
                if aid == accepted:
                    vid += 1
                    acc = at + pd.Timedelta(days=rng.exponential(3))
                    W["Votes"].row(
                        Id=vid,
                        PostId=aid,
                        VoteTypeId=1,
                        CreationDate=_ts(min(acc, END).normalize()),
                    )
            if rng.random() < 0.4:
                vid += 1
                W["Votes"].row(Id=vid, PostId=qid, VoteTypeId=2, CreationDate=_ts(t.normalize()))
            if rng.random() < 0.3:
                cid += 1
                ct = t + pd.Timedelta(minutes=rng.exponential(120))
                if ct < END:
                    W["Comments"].row(
                        Id=cid,
                        PostId=qid,
                        Score=0,
                        Text="sample comment",
                        CreationDate=_ts(ct),
                        UserId=recent[int(rng.integers(0, len(recent)))],
                        ContentLicense="CC BY-SA 4.0",
                    )
    for w_ in W.values():
        w_.close()

    U = Writer(d / "Users.xml", "users")
    U.row(Id=-1, Reputation=1, CreationDate=_ts(START), DisplayName="Community", AccountId=-1)
    for uid, created in users.items():
        U.row(
            Id=uid,
            Reputation=int(rng.lognormal(3, 1.5)),
            CreationDate=_ts(max(created, START)),
            DisplayName=f"user{uid}",
            LastAccessDate=_ts(END - pd.Timedelta(days=1)),
            Location="Somewhere" if rng.random() < 0.4 else None,
            AccountId=uid + 10_000_000,
        )
    U.close()
    T = Writer(d / "Tags.xml", "tags")
    for i, (tg, c) in enumerate(sorted(tag_count.items()), 1):
        T.row(Id=i, TagName=tg, Count=c)
    T.close()
    B = Writer(d / "Badges.xml", "badges")
    B.row(Id=1, UserId=1, Name="Student", Date=_ts(START), Class=3, TagBased="False")
    B.close()
    return {"site": site, "questions": len(q_ids), "posts": pid, "users": len(users)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if config.RAW_DIR.resolve() == Path("/Volumes/Drive3/data") or not config.SAMPLE:
        raise SystemExit("refusing: set SOD_SAMPLE=1 and a sample SOD_RAW_DIR (see Makefile)")
    if config.REFERENCE_DIR.resolve() != REAL_REFERENCE.resolve():
        if config.REFERENCE_DIR.exists():
            shutil.rmtree(config.REFERENCE_DIR)
        shutil.copytree(REAL_REFERENCE, config.REFERENCE_DIR)
        kinds = config.REFERENCE_DIR / "tags_new_post2021_kinds.csv"
        with kinds.open("a") as f:  # half "new technology", half "new version"
            for i, tag in enumerate(NEW_TAGS):
                f.write(f"{tag},{'new' if i % 2 == 0 else 'version'},sample\n")
    for sub in ("figures", "qa", "tables"):
        (config.REPORT_DIR / sub).mkdir(parents=True, exist_ok=True)
    if config.RAW_DIR.exists():
        shutil.rmtree(config.RAW_DIR)
    for i, site in enumerate(config.ALL_SITES):
        rng = np.random.default_rng([args.seed, i])
        s = make_site(site, config.RAW_DIR, rng, args.scale)
        print(
            f"{s['site']:<40} {s['questions']:>8,} questions {s['posts']:>8,} post ids", flush=True
        )


if __name__ == "__main__":
    main()
