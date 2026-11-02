from __future__ import annotations

import fnmatch
import glob
import os
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple

import yaml

CONFIG_FILE = ".trail.yaml"

DEFAULTS = {
    "store": "~/.trail/store",
    "repo": None,
    "harnesses": ["claude", "codex"],
    "session_window_minutes": 240,
    "artifacts": [],
    "exclude": [],
    "max_file_mb": 100,
    "changed_only": True,
    "background": False,
    "s3_endpoint": None,
    "supabase_url": None,
    "pull_max_mb": 5,
    "dashboard_url": "http://localhost:8787",
}

TEMPLATE = """\
# trail: links agent sessions, logs and artifacts to every commit.

# Where traces go:
#   ~/.trail/store                  a local folder
#   supabase://<bucket>/<prefix>    Supabase Storage. Put SUPABASE_URL and
#                                   SUPABASE_SERVICE_ROLE_KEY in the environment or
#                                   ~/.trail/credentials (never in this file).
#   s3://<bucket>/<prefix>          S3-compatible, uses the aws CLI
store: ~/.trail/store

# Name of this repo inside the store.
repo: {name}

# Which harness transcripts to look for.
harnesses: [claude, codex]

# A session counts as active if its transcript changed within this window.
session_window_minutes: 240

# Files and folders copied alongside each commit. Globs are relative to the
# repo root; absolute paths and ../ paths outside the repo work too.
artifacts:
  # - logs/
  # - runs/**/metrics.json
  # - wandb/latest-run/files/output.log

exclude:
  - "**/*.ckpt"
  - "**/*.safetensors"

# Skip any single artifact bigger than this.
max_file_mb: 100

# Only copy artifacts that changed since the last captured commit.
changed_only: true

# Upload after the commit returns instead of blocking it.
background: false

# Pulls skip raw transcript.jsonl files and anything bigger than this; commands fetch
# them when needed, `trail pull --all` gets everything.
pull_max_mb: 5

# Where `trail ui` runs; commits get a Trail-Link: <dashboard_url>/#/<repo>/session/<id> trailer.
dashboard_url: http://localhost:8787

# supabase_url: https://<project-ref>.supabase.co   # if not set in the environment
# s3_endpoint: http://localhost:9000                # MinIO, R2 or other S3-compatible store
"""


def load(root: Path) -> SimpleNamespace:
    path = root / CONFIG_FILE
    data = (yaml.safe_load(path.read_text()) if path.exists() else None) or {}
    merged = {**DEFAULTS, **{k: v for k, v in data.items() if v is not None}}
    merged["repo"] = merged["repo"] or root.name
    merged["artifacts"] = merged["artifacts"] or []
    merged["exclude"] = merged["exclude"] or []
    return SimpleNamespace(root=root, **merged)


def _excluded(rel: str, patterns: List[str]) -> bool:
    name = os.path.basename(rel)
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat.split("/")[-1]):
            return True
    return False


def collect_artifacts(cfg: SimpleNamespace, since: Optional[float]) -> Tuple[List[Tuple[str, Path]], List[str]]:
    """Return (files to copy as (store-relative name, source path), skipped notes)."""
    picked, skipped = {}, []
    limit = cfg.max_file_mb * 1024 * 1024
    for pat in cfg.artifacts:
        pat = os.path.expanduser(str(pat))
        full = pat if os.path.isabs(pat) else str(cfg.root / pat)
        matches: List[Path] = []
        for m in glob.glob(full, recursive=True):
            p = Path(m)
            if p.is_dir():
                matches.extend(f for f in p.rglob("*") if f.is_file())
            else:
                matches.append(p)
        for f in matches:
            f = f.resolve()
            if not f.is_file():
                continue
            try:
                rel = f.relative_to(cfg.root).as_posix()
            except ValueError:
                # ../shared-experiments/x.csv -> _external/shared-experiments/x.csv
                up = Path(os.path.relpath(f, cfg.root)).parts
                rel = "_external/" + "/".join(p for p in up if p != "..")
            if rel.startswith(".git/") or _excluded(rel, cfg.exclude):
                continue
            st = f.stat()
            if st.st_size > limit:
                skipped.append(f"{rel} ({st.st_size // (1024 * 1024)} MB > max_file_mb)")
                continue
            if cfg.changed_only and since and st.st_mtime <= since:
                continue
            picked[rel] = f
    return sorted(picked.items()), skipped
