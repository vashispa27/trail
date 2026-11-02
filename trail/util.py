from __future__ import annotations

import getpass
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional


def git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.rstrip("\n")


def repo_root(cwd: Optional[Path] = None) -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=cwd)).resolve()


def git_dir(root: Path) -> Path:
    return Path(git("rev-parse", "--absolute-git-dir", cwd=root))


def hooks_dir(root: Path) -> Path:
    p = Path(git("rev-parse", "--git-path", "hooks", cwd=root))
    return p if p.is_absolute() else (root / p).resolve()


def user_id(root: Path) -> str:
    who = (git("config", "user.email", cwd=root, check=False)
           or git("config", "user.name", cwd=root, check=False)
           or getpass.getuser())
    return re.sub(r"[^A-Za-z0-9@._-]", "_", who)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… [{len(s) - n} more chars]"
