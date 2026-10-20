"""Progress files for long jobs, and a terminal viewer.

Jobs write `<DATA_DIR>/progress/<job>/<task>.json` every few seconds. The viewer
reads them, so it works from any terminal while the job runs elsewhere:

    make progress            # all jobs
    make progress JOB=posts  # one job
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import IO

from sod import config

PROGRESS_DIR = config.DATA_DIR / "progress"
WRITE_EVERY_S = 2.0


class CountingReader:
    """Wraps a binary file and counts bytes read, so XML parsing can report % done."""

    def __init__(self, f: IO[bytes]):
        self._f = f
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._f.read(size)
        self.bytes_read += len(chunk)
        return chunk


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def write_manifest(job: str, tasks: dict[str, int]) -> None:
    """Record every task in a job and its total size, so pending tasks show too."""
    job_dir = PROGRESS_DIR / job
    if job_dir.exists():
        for old in job_dir.glob("*.json"):
            old.unlink()
    _write_json(job_dir / "_manifest.json", {"job": job, "tasks": tasks, "started": time.time()})


class Reporter:
    def __init__(self, job: str, task: str, total_bytes: int):
        self.path = PROGRESS_DIR / job / f"{task}.json"
        self.state = {
            "task": task,
            "total_bytes": total_bytes,
            "done_bytes": 0,
            "rows": 0,
            "status": "running",
            "started": time.time(),
            "updated": time.time(),
        }
        self._last = 0.0
        self._flush()

    def update(self, done_bytes: int, rows: int) -> None:
        now = time.time()
        if now - self._last < WRITE_EVERY_S:
            return
        self.state.update(done_bytes=done_bytes, rows=rows, updated=now)
        self._flush()

    def finish(self, rows: int, status: str = "done") -> None:
        self.state.update(
            done_bytes=self.state["total_bytes"], rows=rows, status=status, updated=time.time()
        )
        self._flush()

    def _flush(self) -> None:
        self._last = time.time()
        _write_json(self.path, self.state)


# --- viewer ------------------------------------------------------------------


def _bar(frac: float, width: int = 30) -> str:
    frac = min(max(frac, 0.0), 1.0)
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def _fmt_secs(s: float) -> str:
    s = int(max(s, 0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{sec:02d}s"


def render(job_dir: Path) -> tuple[str, bool]:
    manifest = json.loads((job_dir / "_manifest.json").read_text())
    tasks: dict[str, int] = manifest["tasks"]
    states = {}
    for name in tasks:
        p = job_dir / f"{name}.json"
        if p.exists():
            try:
                states[name] = json.loads(p.read_text())
            except json.JSONDecodeError:
                pass

    total = sum(tasks.values())
    done = sum(
        s["total_bytes"] if s["status"] == "done" else s["done_bytes"] for s in states.values()
    )
    elapsed = time.time() - manifest["started"]
    rate = done / elapsed if elapsed > 0 else 0
    eta = (total - done) / rate if rate > 0 else float("nan")
    n_done = sum(1 for s in states.values() if s["status"] == "done")
    failed = [n for n, s in states.items() if s["status"] == "failed"]

    lines = [f"Job: {manifest['job']}   ({n_done}/{len(tasks)} tasks done)"]
    eta_txt = _fmt_secs(eta) if eta == eta else "—"
    lines.append(
        f"  {'OVERALL':<40} {_bar(done / total if total else 1)} {100 * done / max(total, 1):5.1f}%"
        f"  {total / 1e9:6.1f} GB  elapsed {_fmt_secs(elapsed)}  left ~{eta_txt}"
    )
    lines.append("")
    running = [n for n, s in states.items() if s["status"] == "running"]
    order = running + [n for n in tasks if n not in running]
    for name in order:
        s = states.get(name)
        if s is None:
            status, frac, extra = "waiting", 0.0, ""
        else:
            status = s["status"]
            frac = s["done_bytes"] / max(s["total_bytes"], 1)
            secs = s["updated"] - s["started"]
            rps = s["rows"] / secs if secs > 0 else 0
            extra = f"{s['rows']:>12,} rows  {rps:>8,.0f}/s"
        mark = {"done": "✔", "running": "▶", "failed": "✖", "waiting": " "}[status]
        lines.append(f"{mark} {name:<40} {_bar(frac)} {100 * frac:5.1f}%  {extra}")
    if failed:
        lines.append(f"\nFAILED: {', '.join(failed)}")
    finished = n_done + len(failed) == len(tasks)
    return "\n".join(lines), finished


def main(argv: list[str]) -> int:
    job = argv[0] if argv else None
    if not PROGRESS_DIR.exists():
        print(f"No progress files yet in {PROGRESS_DIR}")
        return 1
    try:
        while True:
            job_dirs = sorted(
                d for d in PROGRESS_DIR.iterdir() if d.is_dir() and (job is None or d.name == job)
            )
            screens = [render(d) for d in job_dirs if (d / "_manifest.json").exists()]
            sys.stdout.write("\033[2J\033[H")  # clear screen
            if not screens:
                print("Waiting for a job to start...")
            for text, _ in screens:
                print(text + "\n")
            if screens and all(fin for _, fin in screens):
                print("All done.")
                return 0
            print("(refreshes every 2s — Ctrl-C to close; the job keeps running)")
            time.sleep(2)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
