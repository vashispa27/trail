"""Commit-time capture: link agent sessions and configured artifacts to a commit.

Store layout (under <store>/<repo>/):

  users/<user>/
    sessions/<session_id>/
      meta.json                  harness, title, branch, commits[] with transcript ranges
      transcript.jsonl           raw transcript, latest snapshot
      transcript.md              readable version, grep-friendly
      commits/<sha12>/conversation.md   only the turns that led to that commit
      captures/<ts>/artifacts/   manual `trail capture` snapshots
    commits/<sha12>/
      commit.json                message, author, files, linked sessions, artifacts
      diff.patch
      artifacts/...              whatever .trail.yaml says to keep
  index/commits/<full_sha>.json  sha -> user, sessions (what `trail why` reads)
  repo.json                      git remote and GitHub URL (for the dashboard)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from . import harness, util
from .config import collect_artifacts
from .store import Store

TRAILER = "Trail-Session"
LINK = "Trail-Link"
MAX_DIFF = 2 * 1024 * 1024


def _state_dir(root: Path) -> Path:
    d = util.git_dir(root) / "trail"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- hooks -------------------------------------------------------------------

def sessions_for_commit(cfg: SimpleNamespace, files: Optional[List[str]] = None) -> List[harness.Session]:
    """Sessions to link to the commit being made now.

    An agent committing from its own session names itself. For a human commit, keep
    only recent sessions that edited a staged file since their last linked commit, so
    idle sessions and work that was already committed don't get attributed.
    """
    sessions = harness.discover(cfg.root, cfg.harnesses, cfg.session_window_minutes)
    if os.environ.get("CLAUDE_CODE_SESSION_ID") and len(sessions) == 1:
        return sessions
    staged = files if files is not None else \
        [f for f in util.git("diff", "--cached", "--name-only", cwd=cfg.root).splitlines() if f]
    store = Store(cfg)
    user_dir = Path(cfg.repo) / "users" / util.user_id(cfg.root)
    kept = []
    for s in sessions:
        store.fetch(f"{user_dir}/sessions/{s.session_id}/meta.json")
        meta = util.read_json(store.local / user_dir / "sessions" / s.session_id / "meta.json") or {}
        done = max((c["transcript_range"][1] for c in meta.get("commits", [])), default=0)
        events = harness.parse(s.harness, s.path.read_text(errors="replace").splitlines())
        if any(harness.edit_of(e, cfg.root, f) for e in events if e.line >= done for f in staged):
            kept.append(s)
    return kept


def prepare_commit_msg(cfg: SimpleNamespace, msg_file: str) -> None:
    sessions = sessions_for_commit(cfg)
    util.write_json(_state_dir(cfg.root) / "pending.json", {s.key: str(s.path) for s in sessions})
    base = str(cfg.dashboard_url).rstrip("/")
    for s in sessions:
        link = f"{base}/repos/{urllib.parse.quote(cfg.repo)}/session/{urllib.parse.quote(s.session_id)}"
        util.git("interpret-trailers", "--in-place", "--if-exists", "addIfDifferent",
                 "--trailer", f"{TRAILER}: {s.key}", "--trailer", f"{LINK}: {link}", msg_file, cwd=cfg.root)


def post_commit(cfg: SimpleNamespace) -> None:
    if cfg.background and not os.environ.get("TRAIL_FOREGROUND"):
        log = open(_state_dir(cfg.root) / "hook.log", "a")
        subprocess.Popen([sys.executable, "-m", "trail", "hook", "post-commit"], cwd=cfg.root,
                         env={**os.environ, "TRAIL_FOREGROUND": "1"},
                         stdout=log, stderr=log, start_new_session=True)
        return
    record_commit(cfg, "HEAD")


# --- recording ---------------------------------------------------------------

def _copy_artifacts(cfg: SimpleNamespace, dest: Path, since) -> dict:
    files, skipped = collect_artifacts(cfg, since)
    for rel, src in files:
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    return {"files": [rel for rel, _ in files], "skipped": skipped}


def _commit_info(root: Path, sha: str) -> dict:
    fmt = lambda f: util.git("log", "-1", f"--format={f}", sha, cwd=root)
    files = util.git("show", "--name-status", "--format=", sha, cwd=root).splitlines()
    return {
        "sha": sha,
        "subject": fmt("%s"),
        "message": fmt("%B"),
        "author": fmt("%an <%ae>"),
        "date": fmt("%aI"),
        "branch": util.git("rev-parse", "--abbrev-ref", "HEAD", cwd=root, check=False),
        "files": [f.replace("\t", " ") for f in files if f],
    }


def _commit_line(lines: List[str], subject: str) -> int:
    """Transcript end for a commit recorded after the fact: just past the agent's `git commit` call."""
    # First mention: later lines can repeat the command (request logs, tool output).
    for i in range(len(lines)):
        if "git commit" in lines[i] and subject in lines[i]:
            return min(i + 2, len(lines))  # include the tool result line
    return len(lines)


def _record_session(cfg, store: Store, user_dir: Path, h: str, sid: str, src: Path, info: dict,
                    backfill: bool) -> dict:
    short = info["sha"][:12]
    sdir = user_dir / "sessions" / sid
    sdir.mkdir(parents=True, exist_ok=True)
    raw = src.read_text(errors="replace")
    lines = raw.splitlines()
    (sdir / "transcript.jsonl").write_text(raw)

    # The local mirror may be missing or stale; earlier commits' ranges live in the store.
    store.fetch(store._rel(sdir / "meta.json"))
    meta = util.read_json(sdir / "meta.json") or {"session_id": sid, "harness": h, "source": str(src), "commits": []}
    known = {c["sha"]: c for c in meta["commits"]}
    if info["sha"] in known:  # re-recording: the range was fixed when the commit happened
        span = known.pop(info["sha"])["transcript_range"]
    else:
        # At commit time the transcript ends at the commit; when backfilling it has moved on.
        end = _commit_line(lines, info["subject"]) if backfill else len(lines)
        start = max((c["transcript_range"][1] for c in known.values() if c["transcript_range"][1] <= end), default=0)
        span = [start, end]
    if span[1] > len(lines):  # transcript was rewritten (e.g. compaction); take it all
        span = [0, len(lines)]
    start = span[0]

    events = harness.parse(h, lines)
    title = next((e.text.strip() for e in events if harness.is_prompt(e)), "")
    title = " ".join(re.sub(r"</?[A-Za-z_-]+[^>]*>", " ", title).split())[:140]
    (sdir / "transcript.md").write_text(harness.render(events, f"{h} session {sid}"))
    conv = sdir / "commits" / short
    conv.mkdir(parents=True, exist_ok=True)
    (conv / "conversation.md").write_text(
        harness.render([e for e in events if span[0] <= e.line < span[1]],
                       f"Conversation behind {short}: {info['subject']}"))

    known[info["sha"]] = {"sha": info["sha"], "subject": info["subject"], "date": info["date"],
                          "transcript_range": span}
    meta["commits"] = sorted(known.values(), key=lambda c: c["transcript_range"][1])
    meta.update(title=meta.get("title") or title, branch=info["branch"], last_seen=_now())
    util.write_json(sdir / "meta.json", meta)
    return {"key": f"{h}:{sid}", "harness": h, "session_id": sid, "title": meta["title"],
            "dir": store._rel(sdir), "transcript_range": span}


def record_commit(cfg: SimpleNamespace, rev: str = "HEAD", backfill: bool = False) -> dict:
    root, store = cfg.root, Store(cfg)
    state_dir = _state_dir(root)
    state = util.read_json(state_dir / "state.json") or {}
    pending = util.read_json(state_dir / "pending.json") or {}
    started = time.time()

    sha = util.git("rev-parse", rev, cwd=root)
    info = _commit_info(root, sha)
    keys = [k.strip() for k in util.git("log", "-1", f"--format=%(trailers:key={TRAILER},valueonly)", sha,
                                        cwd=root).splitlines() if k.strip()]
    user = util.user_id(root)
    repo_dir = store.local / cfg.repo
    user_dir = repo_dir / "users" / user
    cdir = user_dir / "commits" / sha[:12]
    cdir.mkdir(parents=True, exist_ok=True)

    info["artifacts"] = _copy_artifacts(cfg, cdir / "artifacts", state.get("last_capture"))
    # List what is on disk, so re-recording a commit keeps artifacts copied the first time.
    adir = cdir / "artifacts"
    info["artifacts"]["files"] = sorted(p.relative_to(adir).as_posix() for p in adir.rglob("*") if p.is_file())
    diff = util.git("show", "--stat", "--patch", "--format=", sha, cwd=root)
    (cdir / "diff.patch").write_text(diff[:MAX_DIFF])

    sessions: List[dict] = []
    for key in keys:
        h, _, sid = key.partition(":")
        src = Path(pending[key]) if key in pending else harness.find_session(h, sid)
        if src and src.exists():
            sessions.append(_record_session(cfg, store, user_dir, h, sid, src, info, backfill))
    info["sessions"] = sessions
    util.write_json(cdir / "commit.json", info)

    index = repo_dir / "index" / "commits" / f"{sha}.json"
    util.write_json(index, {"sha": sha, "subject": info["subject"], "date": info["date"], "user": user,
                            "branch": info["branch"], "commit_dir": store._rel(cdir), "sessions": sessions})
    state["last_capture"] = started
    util.write_json(state_dir / "state.json", state)
    (state_dir / "pending.json").unlink(missing_ok=True)

    print(f"trail: {sha[:12]} linked {len(sessions)} session(s), {len(info['artifacts']['files'])} artifact(s)"
          f" -> {store.short(cdir)}", file=sys.stderr)
    _push(store, [cdir, index, write_repo_info(cfg, store)] + [store.local / s["dir"] for s in sessions])
    return info


def github_url(remote: str) -> Optional[str]:
    """git@github.com:o/r.git, ssh://git@github.com/o/r, https://github.com/o/r.git -> https://github.com/o/r"""
    m = re.match(r"^(?:\w+://)?(?:[^@/]+@)?github\.com[:/]([^/]+)/(.+?)(?:\.git)?/?$", remote.strip())
    return f"https://github.com/{m.group(1)}/{m.group(2)}" if m else None


def write_repo_info(cfg: SimpleNamespace, store: Store) -> Path:
    """<repo>/repo.json: where the code lives, for the dashboard."""
    remote = util.git("remote", "get-url", "origin", cwd=cfg.root, check=False)
    path = store.local / cfg.repo / "repo.json"
    util.write_json(path, {"name": cfg.repo, "remote": remote or None, "github": github_url(remote) if remote else None})
    return path


def _push(store: Store, paths: List[Path]) -> None:
    # The local copy is already written; a failed upload is retried by `trail push`.
    try:
        n = store.push(paths)
        if store.remote:
            print(f"trail: uploaded {n} file(s) to {store.remote}", file=sys.stderr)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print(f"trail: warning: saved locally, upload failed: {e}", file=sys.stderr)


def capture_now(cfg: SimpleNamespace) -> None:
    """Snapshot active sessions and artifacts without a commit (dead ends, long runs)."""
    store = Store(cfg)
    sessions = harness.discover(cfg.root, cfg.harnesses, cfg.session_window_minutes)
    user_dir = store.local / cfg.repo / "users" / util.user_id(cfg.root)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    pushed = []
    for s in sessions or [harness.Session("none", "_no-session", Path())]:
        sdir = user_dir / "sessions" / s.session_id
        cap = sdir / "captures" / stamp
        cap.mkdir(parents=True, exist_ok=True)
        if s.path.is_file():
            raw = s.path.read_text(errors="replace")
            (sdir / "transcript.jsonl").write_text(raw)
            (sdir / "transcript.md").write_text(
                harness.render(harness.parse(s.harness, raw.splitlines()), f"{s.harness} session {s.session_id}"))
        art = _copy_artifacts(cfg, cap / "artifacts", None)
        print(f"trail: captured {s.key} with {len(art['files'])} artifact(s) -> {store.short(cap)}", file=sys.stderr)
        pushed.append(sdir)
    _push(store, pushed)
