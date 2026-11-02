from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import List

from . import capture, config, harness, util
from .store import Store

PKG_ROOT = Path(__file__).resolve().parent.parent
HOOKS = ("prepare-commit-msg", "post-commit")
MARK = "# installed by trail"


def _hook_script(name: str) -> str:
    return (f"#!/bin/sh\n{MARK}\n"
            f'if [ -x "$0.pre-trail" ]; then "$0.pre-trail" "$@" || exit $?; fi\n'
            f'PYTHONPATH={shlex.quote(str(PKG_ROOT))}"${{PYTHONPATH:+:$PYTHONPATH}}" '
            f'{shlex.quote(sys.executable)} -m trail hook {name} "$@" || true\n')


# --- commands ----------------------------------------------------------------

def cmd_init(cfg: SimpleNamespace, args) -> int:
    cfile = cfg.root / config.CONFIG_FILE
    if not cfile.exists():
        cfile.write_text(config.TEMPLATE.format(name=cfg.root.name))
        print(f"wrote {cfile}")
    hdir = util.hooks_dir(cfg.root)
    hdir.mkdir(parents=True, exist_ok=True)
    for name in HOOKS:
        hook = hdir / name
        if hook.exists() and MARK not in hook.read_text(errors="replace"):
            hook.rename(hook.with_name(name + ".pre-trail"))  # keep the existing hook, chain to it
        hook.write_text(_hook_script(name))
        hook.chmod(0o755)
        print(f"installed {hook}")
    cfg = config.load(cfg.root)
    store = Store(cfg)
    if store.sb:
        try:
            made = store.sb.ensure_bucket()
            print(f"{'created' if made else 'using'} supabase bucket {store.sb.bucket} at {store.sb.base}")
        except RuntimeError as e:
            print(f"warning: {e}", file=sys.stderr)
    capture._push(store, [capture.write_repo_info(cfg, store)])
    print(f"store: {store.where(store.local / cfg.repo)}")
    return 0


def cmd_hook(cfg, args) -> int:
    # A tracing tool must never block a commit.
    try:
        if args.name == "prepare-commit-msg":
            capture.prepare_commit_msg(cfg, args.args[0])
        else:
            capture.post_commit(cfg)
    except Exception as e:  # noqa: BLE001
        print(f"trail: warning: {args.name} failed: {e}", file=sys.stderr)
    return 0


def cmd_status(cfg, args) -> int:
    # Judge against everything changed or new, not just what is staged yet.
    changed = util.git("diff", "HEAD", "--name-only", cwd=cfg.root).splitlines()
    changed += util.git("ls-files", "--others", "--exclude-standard", cwd=cfg.root).splitlines()
    sessions = capture.sessions_for_commit(cfg, [f for f in changed if f])
    print(f"repo: {cfg.repo}   user: {util.user_id(cfg.root)}   store: {Store(cfg).where(Store(cfg).local / cfg.repo)}")
    print(f"\nsessions that edited the current changes ({len(sessions)}):")
    for s in sessions:
        print(f"  {s.key}\n    {s.path}")
    state = util.read_json(util.git_dir(cfg.root) / "trail" / "state.json") or {}
    files, skipped = config.collect_artifacts(cfg, state.get("last_capture"))
    print(f"\nartifacts the next commit will copy ({len(files)}):")
    for rel, _ in files:
        print(f"  {rel}")
    for s in skipped:
        print(f"  skipped {s}")
    return 0


def cmd_capture(cfg, args) -> int:
    capture.capture_now(cfg)
    return 0


def cmd_record(cfg, args) -> int:
    capture.record_commit(cfg, args.rev, backfill=True)
    return 0


def _index(cfg, store: Store) -> List[dict]:
    store.pull(f"{cfg.repo}/index")
    rows = [util.read_json(f) for f in (store.local / cfg.repo / "index" / "commits").glob("*.json")]
    return sorted((r for r in rows if r), key=lambda r: r["date"], reverse=True)


def cmd_log(cfg, args) -> int:
    for r in _index(cfg, Store(cfg))[: args.n]:
        print(f"{r['sha'][:12]}  {r['date'][:16]}  {r['user']:<24} {r['subject']}")
        for s in r["sessions"]:
            print(f"    └ {s['key']}  {s['title'][:70]}")
    return 0


def _tree(base: Path, d: Path, left: int = 0) -> None:
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        print(f"    {f.relative_to(base)}  ({f.stat().st_size:,} B)")
    if left:
        print(f"    + {left} file(s) not downloaded (raw transcripts, large files): "
              f"trail pull {d.relative_to(base)} --all")


def cmd_show(cfg, args) -> int:
    store = Store(cfg)
    base = store.local / cfg.repo
    hits = [r for r in _index(cfg, store) if r["sha"].startswith(args.ref)]
    if hits:
        r = hits[0]
        left = store.pull(r["commit_dir"])[1]
        print(f"commit {r['sha']}  {r['subject']}\n  {store.where(store.local / r['commit_dir'])}")
        _tree(base, store.local / r["commit_dir"], left)
        for s in r["sessions"]:
            left = store.pull(s["dir"])[1]
            print(f"\nsession {s['key']}  {s['title'][:80]}\n  {store.where(store.local / s['dir'])}")
            _tree(base, store.local / s["dir"], left)
        return 0
    store.pull(cfg.repo)
    for sdir in base.glob(f"users/*/sessions/{args.ref}*"):
        meta = util.read_json(sdir / "meta.json") or {}
        print(f"session {meta.get('harness')}:{meta.get('session_id')}  {meta.get('title', '')[:80]}")
        for c in meta.get("commits", []):
            print(f"  commit {c['sha'][:12]}  {c['subject']}  (transcript lines {c['transcript_range']})")
        _tree(base, sdir)
        return 0
    print(f"nothing in the trail matches {args.ref}", file=sys.stderr)
    return 1


def _say(label: str, text: str, n: int = 900) -> None:
    body = util.clip(text.strip(), n).replace("\n", "\n    ")
    print(f"  {label}:\n    {body}")


def cmd_why(cfg, args) -> int:
    store = Store(cfg)
    file, _, line = args.target.rpartition(":")
    if not file or not line.isdigit():
        print("usage: trail why <file>:<line>", file=sys.stderr)
        return 2
    rel = Path(file).resolve().relative_to(cfg.root).as_posix()
    blame = util.git("blame", "-L", f"{line},{line}", "--porcelain", "--", rel, cwd=cfg.root).splitlines()
    sha = blame[0].split()[0]
    code = next((b[1:] for b in blame if b.startswith("\t")), "")
    print(f"{rel}:{line}  {code.strip()}")
    if set(sha) == {"0"}:
        print("  not committed yet")
        return 1

    store.fetch(f"{cfg.repo}/index/commits/{sha}.json")
    idx = util.read_json(store.local / cfg.repo / "index" / "commits" / f"{sha}.json")
    subject = util.git("log", "-1", "--format=%s  (%an, %ar)", sha, cwd=cfg.root)
    print(f"  last changed in {sha[:12]}  {subject}")
    if not idx or not idx["sessions"]:
        print("  no agent session recorded for this commit")
        return 1

    needle = code.strip()
    for s in idx["sessions"]:
        store.fetch(f"{s['dir']}/transcript.jsonl")  # raw transcripts are not part of a normal pull
        sdir = store.local / s["dir"]
        lines = (sdir / "transcript.jsonl").read_text(errors="replace").splitlines()
        start, end = s["transcript_range"]
        events = harness.parse(s["harness"], lines[:end])
        print(f"\n  session {s['key']}  \"{s['title'][:80]}\"")

        # The tool call that wrote this file: prefer one whose written text contains the
        # blamed line, then explicit file edits, then mentions; search this commit's turns first.
        best, best_score = None, -1
        for floor in (start, 0):
            for i, e in enumerate(events):
                if e.line < floor:
                    continue
                hit = harness.edit_of(e, cfg.root, rel)
                if not hit:
                    continue
                score = hit[0] + (2 if harness.contains_line(hit[1], needle) else 0)
                if score >= best_score:
                    best, best_score = i, score
            if best is not None:
                break

        if best is None:
            prompts = [e for e in events if e.line >= start and harness.is_prompt(e)]
            if prompts:
                _say("asked", prompts[-1].text, 600)
        else:
            j = best
            while j > 0 and not harness.is_prompt(events[j]):
                j -= 1
            if harness.is_prompt(events[j]):
                _say("asked", events[j].text, 600)
            # Reasoning from this commit's own turns only; a turn can span several commits.
            reasoning = [e for e in events[j + 1:best] if e.line >= start
                         and e.role == "assistant" and e.kind in ("text", "thinking")]
            for e in reasoning[-3:]:
                _say("reasoning" if e.kind == "thinking" else "said", e.text)
            _say(f"edit ({events[best].tool})", harness.edit_of(events[best], cfg.root, rel)[1], 500)
        print(f"  full conversation: {store.short(sdir / 'commits' / sha[:12] / 'conversation.md')}")

    cj = util.read_json(store.local / idx["commit_dir"] / "commit.json") or {}
    arts = (cj.get("artifacts") or {}).get("files", [])
    if arts:
        print(f"\n  artifacts saved with this commit ({store.short(store.local / idx['commit_dir'] / 'artifacts')}):")
        for a in arts:
            print(f"    {a}")
    return 0


def cmd_grep(cfg, args) -> int:
    store = Store(cfg)
    left = store.pull(cfg.repo)[1]
    if left:
        print(f"(searching the local mirror; {left} raw transcript/large file(s) not downloaded, "
              f"`trail pull --all` to include them)", file=sys.stderr)
    base = store.local / cfg.repo
    if shutil.which("rg"):
        cmd = ["rg", "-n", "--glob", "!*.jsonl", *args.extra, args.pattern, "."]
    else:
        cmd = ["grep", "-rn", "--exclude=*.jsonl", *args.extra, args.pattern, "."]
    return subprocess.call(cmd, cwd=base)


def cmd_pull(cfg, args) -> int:
    store = Store(cfg)
    rel = f"{cfg.repo}/{args.path.strip('/')}".rstrip("/")
    got, left = store.pull(rel, everything=args.all)
    print(f"downloaded {got} file(s)" + (f", left {left} remote (--all to include)" if left else ""),
          file=sys.stderr)
    print(store.local / rel)
    return 0


def cmd_push(cfg, args) -> int:
    store = Store(cfg)
    n = store.push([store.local / cfg.repo])
    print(f"uploaded {n} file(s) to {store.remote or store.local}")
    return 0


def cmd_path(cfg, args) -> int:
    print(Store(cfg).local / cfg.repo)
    return 0


def cmd_ui(cfg, args) -> int:
    from . import ui
    return ui.serve(cfg, args.port, args.host)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trail", description="Link agent sessions, logs and artifacts to git commits.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write .trail.yaml and install git hooks").set_defaults(fn=cmd_init)
    h = sub.add_parser("hook", help="(called by git hooks)")
    h.add_argument("name", choices=HOOKS)
    h.add_argument("args", nargs="*")
    h.set_defaults(fn=cmd_hook)
    sub.add_parser("status", help="sessions and artifacts the next commit will link").set_defaults(fn=cmd_status)
    sub.add_parser("capture", help="snapshot sessions + artifacts without committing").set_defaults(fn=cmd_capture)
    r = sub.add_parser("record", help="record (or re-record) an existing commit")
    r.add_argument("rev", nargs="?", default="HEAD")
    r.set_defaults(fn=cmd_record)
    lg = sub.add_parser("log", help="commits in the trail with their sessions")
    lg.add_argument("-n", type=int, default=20)
    lg.set_defaults(fn=cmd_log)
    s = sub.add_parser("show", help="files stored for a commit sha or session id (prefix ok)")
    s.add_argument("ref")
    s.set_defaults(fn=cmd_show)
    w = sub.add_parser("why", help="why does this line exist? blame -> commit -> session -> reasoning")
    w.add_argument("target", metavar="FILE:LINE")
    w.set_defaults(fn=cmd_why)
    g = sub.add_parser("grep", help="search every transcript, log and artifact in the trail (extra flags go to rg)")
    g.add_argument("pattern")
    g.set_defaults(fn=cmd_grep)
    pl = sub.add_parser("pull", help="update the local mirror (skips raw transcripts and large files)")
    pl.add_argument("path", nargs="?", default="", help="part of the trail, e.g. users/alice/commits/1a2b3c")
    pl.add_argument("--all", action="store_true", help="include raw transcripts and large files")
    pl.set_defaults(fn=cmd_pull)
    sub.add_parser("push", help="upload anything not yet in the remote store").set_defaults(fn=cmd_push)
    sub.add_parser("path", help="print the local folder holding this repo's trail").set_defaults(fn=cmd_path)
    u = sub.add_parser("ui", help="web dashboard over the store (repos, commits, sessions, files)")
    u.add_argument("--port", type=int, default=8787)
    u.add_argument("--host", default="127.0.0.1")
    u.set_defaults(fn=cmd_ui)
    args, args.extra = ap.parse_known_args(argv)
    if args.extra and args.cmd != "grep":
        ap.error(f"unrecognized arguments: {' '.join(args.extra)}")

    try:
        root = util.repo_root()
    except RuntimeError:
        print("trail: not inside a git repository", file=sys.stderr)
        return 0 if args.cmd == "hook" else 1
    return args.fn(config.load(root), args)
