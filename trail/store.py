"""Storage: everything is written to a local tree first, then synced to the remote store.

The local tree is what you grep and point agents at. For a local store it *is* the
store; for a remote one it is a cache under ~/.trail/cache/<scheme>/...

Remote stores:
  supabase://<bucket>/<prefix>   Supabase Storage over its REST API (stdlib only).
                                 Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, from
                                 the environment or ~/.trail/credentials.
  s3://<bucket>/<prefix>         any S3-compatible store, via the aws CLI.

Pulls are partial by default: raw transcript.jsonl files and anything bigger than
pull_max_mb stay remote until a command needs them (`trail why` fetches the one
transcript it reads) or you ask with `trail pull --all`.
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Tuple

from . import util

MB = 1024 * 1024
RAW = "transcript.jsonl"
MANIFEST = ".trail-sync.json"


def _credentials() -> Dict[str, str]:
    """KEY=VALUE lines from ~/.trail/credentials, overridden by the environment."""
    out: Dict[str, str] = {}
    path = Path(os.environ.get("TRAIL_CREDENTIALS", "~/.trail/credentials")).expanduser()
    if path.is_file():
        for line in path.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                out[k.strip().removeprefix("export ").strip()] = v.strip().strip("'\"")
    out.update({k: v for k, v in os.environ.items() if k.startswith("SUPABASE_")})
    return out


class Supabase:
    """Just enough of the Supabase Storage REST API: upload, download, recursive list."""

    def __init__(self, bucket: str, project_url: Optional[str]):
        creds = _credentials()
        self.bucket = bucket
        self.base = (creds.get("SUPABASE_URL") or project_url or "").rstrip("/")
        self.key = creds.get("SUPABASE_SERVICE_ROLE_KEY") or creds.get("SUPABASE_KEY") or ""

    def _req(self, method: str, path: str, body: Optional[bytes] = None, ctype: str = "application/json",
             extra: Optional[dict] = None) -> bytes:
        if not self.base or not self.key:
            raise RuntimeError("supabase store needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
                               "(environment or ~/.trail/credentials)")
        headers = {"Authorization": f"Bearer {self.key}", "apikey": self.key, "Content-Type": ctype, **(extra or {})}
        req = urllib.request.Request(f"{self.base}/storage/v1/{path}", data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"supabase {method} {path}: {e.code} {e.read().decode(errors='replace')[:200]}") from None

    def _obj(self, key: str) -> str:
        return f"object/{self.bucket}/{urllib.parse.quote(key, safe='/')}"

    def ensure_bucket(self) -> bool:
        """Create the bucket (private) if missing. True if it was created."""
        try:
            self._req("GET", f"bucket/{self.bucket}")
            return False
        except RuntimeError:
            self._req("POST", "bucket", json.dumps({"id": self.bucket, "name": self.bucket, "public": False}).encode())
            return True

    def upload(self, key: str, path: Path) -> None:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._req("POST", self._obj(key), path.read_bytes(), ctype, {"x-upsert": "true"})

    def read(self, key: str) -> bytes:
        return self._req("GET", f"object/authenticated/{self.bucket}/{urllib.parse.quote(key, safe='/')}")

    def download(self, key: str, dest: Path) -> None:
        data = self.read(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)

    def list(self, prefix: str) -> Dict[str, Tuple[int, str]]:
        """Every object under `prefix` (recursive): key -> (size, updated_at)."""
        out: Dict[str, Tuple[int, str]] = {}
        folders = [prefix.strip("/")]
        while folders:
            folder = folders.pop()
            offset = 0
            while True:
                body = {"prefix": folder + "/" if folder else "", "limit": 1000, "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"}}
                items = json.loads(self._req("POST", f"object/list/{self.bucket}", json.dumps(body).encode()))
                for it in items:
                    key = f"{folder}/{it['name']}" if folder else it["name"]
                    if it.get("id") is None:  # a folder
                        folders.append(key)
                    else:
                        out[key] = (int((it.get("metadata") or {}).get("size") or 0), it.get("updated_at") or "")
                if len(items) < 1000:
                    break
                offset += 1000
        return out


class Store:
    def __init__(self, cfg: SimpleNamespace):
        url = str(cfg.store).rstrip("/")
        self.endpoint = cfg.s3_endpoint
        self.pull_max = int(cfg.pull_max_mb * MB)
        cache = Path(os.environ.get("TRAIL_CACHE", "~/.trail/cache")).expanduser()
        self.kind, self.remote, self.sb, self.prefix = "local", None, None, ""
        if url.startswith("s3://"):
            self.kind, self.remote = "s3", url
            self.local = cache / url[len("s3://"):]
        elif url.startswith("supabase://"):
            bucket, _, self.prefix = url[len("supabase://"):].partition("/")
            self.kind, self.remote = "supabase", url
            self.sb = Supabase(bucket, cfg.supabase_url)
            host = urllib.parse.urlparse(self.sb.base).netloc or "unconfigured"
            self.local = cache / "supabase" / host / bucket / self.prefix
        else:
            p = Path(os.path.expanduser(url))
            self.local = p if p.is_absolute() else (cfg.root / p).resolve()
        self.local.mkdir(parents=True, exist_ok=True)

    # --- helpers -------------------------------------------------------------

    def _aws(self, *args: str, check: bool = True) -> int:
        cmd = ["aws", "s3", *args, "--only-show-errors"]
        if self.endpoint:
            cmd += ["--endpoint-url", self.endpoint]
        return subprocess.run(cmd, check=check).returncode

    def _rel(self, p: Path) -> str:
        return p.relative_to(self.local).as_posix()

    def _key(self, rel: str) -> str:
        return f"{self.prefix}/{rel}".strip("/") if self.prefix else rel

    def _manifest(self) -> dict:
        return util.read_json(self.local / MANIFEST) or {}

    @staticmethod
    def _sig(p: Path) -> List[int]:
        st = p.stat()
        return [st.st_size, st.st_mtime_ns]

    # --- sync ----------------------------------------------------------------

    def push(self, paths: Iterable[Path]) -> int:
        """Upload what changed under `paths` since the last sync. Returns files uploaded."""
        if self.kind == "s3":
            for p in paths:
                rel = self._rel(p)
                if p.is_dir():
                    self._aws("sync", str(p), f"{self.remote}/{rel}")
                elif p.exists():
                    self._aws("cp", str(p), f"{self.remote}/{rel}")
            return 0
        if self.kind != "supabase":
            return 0
        files: List[Path] = []
        for p in paths:
            files += [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else ([p] if p.is_file() else [])
        man = self._manifest()
        todo = [f for f in files if f.name != MANIFEST and not f.name.endswith(".part")
                and man.get(self._rel(f), {}).get("sig") != self._sig(f)]

        def up(f: Path):
            try:
                self.sb.upload(self._key(self._rel(f)), f)
                return f, None
            except (RuntimeError, OSError) as e:
                return f, str(e)

        failed = []
        with ThreadPoolExecutor(8) as pool:
            for f, err in pool.map(up, todo):
                if err:
                    failed.append(f"{self._rel(f)}: {err}")
                else:
                    man[self._rel(f)] = {"sig": self._sig(f)}  # remote stamp learned on next pull
        util.write_json(self.local / MANIFEST, man)
        if failed:
            raise RuntimeError(f"{len(failed)} upload(s) failed, retry with `trail push`:\n  " + "\n  ".join(failed[:5]))
        return len(todo)

    def pull(self, rel: str = "", everything: bool = False) -> Tuple[int, int]:
        """Bring the local tree up to date under `rel`. Returns (downloaded, left remote)."""
        if self.kind == "s3":
            skip = [] if everything else ["--exclude", f"*{RAW}"]
            self._aws("sync", f"{self.remote}/{rel}".rstrip("/"), str(self.local / rel), *skip, check=False)
            return 0, 0
        if self.kind != "supabase":
            return 0, 0
        pre = self._key("")
        listing = {k[len(pre):].lstrip("/") if pre else k: v for k, v in self.sb.list(self._key(rel)).items()}
        return self._sync_down(listing, everything)

    def fetch(self, rel: str) -> None:
        """Make sure one file is local and current (no size or name filter)."""
        if self.kind == "s3":
            self._aws("cp", f"{self.remote}/{rel}", str(self.local / rel), check=False)
        elif self.kind == "supabase":
            parent = rel.rpartition("/")[0]
            pre = self._key("")
            listing = {k[len(pre):].lstrip("/") if pre else k: v for k, v in self.sb.list(self._key(parent)).items()}
            self._sync_down({rel: listing[rel]} if rel in listing else {}, everything=True)

    def _sync_down(self, listing: Dict[str, Tuple[int, str]], everything: bool) -> Tuple[int, int]:
        man = self._manifest()
        todo, left = [], 0
        for rel, (size, updated) in listing.items():
            local, m = self.local / rel, man.get(rel, {})
            if not everything and (rel.endswith(RAW) or size > self.pull_max):
                left += not local.is_file()  # fetched earlier on demand: stays, but not refreshed
                continue
            if local.is_file():
                if m.get("remote") == updated:
                    continue
                # We uploaded this exact file ourselves; just learn its remote stamp.
                if "remote" not in m and m.get("sig") == self._sig(local) and local.stat().st_size == size:
                    man[rel] = {**m, "remote": updated}
                    continue
            todo.append((rel, updated))

        def down(item):
            rel, updated = item
            self.sb.download(self._key(rel), self.local / rel)
            return rel, updated

        with ThreadPoolExecutor(8) as pool:
            for rel, updated in pool.map(down, todo):
                man[rel] = {"sig": self._sig(self.local / rel), "remote": updated}
        util.write_json(self.local / MANIFEST, man)
        return len(todo), left

    # --- display -------------------------------------------------------------

    def where(self, p: Path) -> str:
        return f"{self.remote}/{self._rel(p)}" if self.remote else str(p)

    def short(self, p: Path) -> str:
        """Path as shown in command output: relative to the repo's trail folder (`trail path`)."""
        return "/".join(Path(self._rel(p)).parts[1:])
