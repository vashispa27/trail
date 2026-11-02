"""`trail ui`: run the Next.js dashboard in web/ against this repo's store.

The dashboard reads the store itself (Supabase Storage or a local folder); this only
points it there through environment variables and starts `next dev`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from .store import Store

WEB = Path(__file__).resolve().parent.parent / "web"


def serve(cfg: SimpleNamespace, port: int, host: str = "127.0.0.1") -> int:
    store = Store(cfg)
    if store.kind == "s3":
        print("trail ui: s3:// stores are not supported yet (use supabase:// or a local folder)", file=sys.stderr)
        return 1
    if not (WEB / "package.json").is_file() or not shutil.which("npm"):
        print(f"trail ui: needs Node.js (npm) and the dashboard in {WEB}", file=sys.stderr)
        return 1
    if not (WEB / "node_modules").is_dir():
        print("trail ui: installing dashboard dependencies (first run)", file=sys.stderr)
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=WEB, check=True)

    env = {**os.environ, "TRAIL_STORE": store.remote or str(store.local)}
    if store.kind == "supabase":
        env.update(SUPABASE_URL=store.sb.base, SUPABASE_SERVICE_ROLE_KEY=store.sb.key)
    print(f"trail ui: {env['TRAIL_STORE']} at http://{host}:{port}/repos", flush=True)
    try:
        return subprocess.run(["npx", "next", "dev", "-p", str(port), "-H", host], cwd=WEB, env=env).returncode
    except KeyboardInterrupt:
        return 0
