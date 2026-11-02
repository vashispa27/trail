"""Find agent sessions (Claude Code, Codex) for a repo and normalize their transcripts."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

from .util import clip


def claude_dir() -> Path:
    return Path(os.environ.get("TRAIL_CLAUDE_DIR", "~/.claude/projects")).expanduser()


def codex_dir() -> Path:
    return Path(os.environ.get("TRAIL_CODEX_DIR", "~/.codex/sessions")).expanduser()


@dataclass
class Session:
    harness: str
    session_id: str
    path: Path

    @property
    def key(self) -> str:
        return f"{self.harness}:{self.session_id}"


# --- discovery ---------------------------------------------------------------

def _inside(cwd: Optional[str], root: Path) -> bool:
    if not cwd:
        return False
    try:
        Path(cwd).resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _first(path: Path, limit: int, pick) -> Any:
    with path.open(errors="replace") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            try:
                v = pick(json.loads(line))
            except (ValueError, AttributeError):
                continue
            if v:
                return v
    return None


def _claude_cwd(path: Path) -> Optional[str]:
    return _first(path, 300, lambda d: d.get("cwd"))


def _codex_meta(path: Path) -> dict:
    return _first(path, 20, lambda d: d.get("payload") if d.get("type") == "session_meta" else None) or {}


def discover(root: Path, harnesses: List[str], window_minutes: int) -> List[Session]:
    """Sessions that should be linked to a commit made right now in `root`."""
    # An agent committing from inside its own session tells us exactly which one it is.
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if sid and "claude" in harnesses:
        hit = find_session("claude", sid)
        if hit:
            return [Session("claude", sid, hit)]

    # Otherwise (a human committing from a terminal): every session in this repo
    # whose transcript moved recently.
    cutoff = time.time() - window_minutes * 60
    found: List[Session] = []
    if "claude" in harnesses:
        found += _recent_claude(root, cutoff)
    if "codex" in harnesses:
        found += _recent_codex(root, cutoff)
    return found


def _recent_claude(root: Path, cutoff: float) -> List[Session]:
    base, out = claude_dir(), []
    if not base.is_dir():
        return out
    # Claude Code names project dirs after the cwd with every non-alphanumeric char as "-".
    enc = re.sub(r"[^A-Za-z0-9-]", "-", str(root))
    for d in base.iterdir():
        if not d.is_dir() or not (d.name == enc or d.name.startswith(enc + "-")):
            continue
        for f in d.glob("*.jsonl"):
            if f.stat().st_mtime >= cutoff and _inside(_claude_cwd(f), root):
                out.append(Session("claude", f.stem, f))
    return out


def _recent_codex(root: Path, cutoff: float) -> List[Session]:
    base, out = codex_dir(), []
    if not base.is_dir():
        return out
    # Rollouts live in YYYY/MM/DD of the day the session started; a session can stay
    # active for days, so look back a week.
    day = min(datetime.fromtimestamp(cutoff).date(), datetime.now().date() - timedelta(days=7))
    while day <= datetime.now().date():
        d = base / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
        for f in (d.glob("rollout-*.jsonl") if d.is_dir() else []):
            if f.stat().st_mtime < cutoff:
                continue
            meta = _codex_meta(f)
            if _inside(meta.get("cwd"), root):
                out.append(Session("codex", meta.get("id") or f.stem[-36:], f))
        day += timedelta(days=1)
    return out


def find_session(harness: str, sid: str) -> Optional[Path]:
    if harness == "claude":
        hits = list(claude_dir().glob(f"*/{sid}.jsonl"))
    else:
        hits = list(codex_dir().rglob(f"rollout-*{sid}.jsonl"))
    return hits[0] if hits else None


# --- normalized events -------------------------------------------------------

@dataclass
class Event:
    line: int     # line number in the raw transcript
    role: str     # user | assistant | tool
    kind: str     # text | thinking | tool_call | tool_result
    text: str
    tool: str = ""
    input: Any = None


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text"))
    return ""


def _as_text(v: Any) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)


def parse(harness: str, lines: List[str]) -> List[Event]:
    return _parse_claude(lines) if harness == "claude" else _parse_codex(lines)


def _parse_claude(lines: List[str]) -> List[Event]:
    out: List[Event] = []
    for i, line in enumerate(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        role = d.get("type")
        if role not in ("user", "assistant"):
            continue
        content = (d.get("message") or {}).get("content")
        if isinstance(content, str):
            if content.strip():
                out.append(Event(i, role, "text", content))
            continue
        for b in content or []:
            bt = b.get("type")
            if bt == "text" and b.get("text", "").strip():
                out.append(Event(i, role, "text", b["text"]))
            elif bt == "thinking" and b.get("thinking", "").strip():
                out.append(Event(i, "assistant", "thinking", b["thinking"]))
            elif bt == "tool_use":
                inp = b.get("input")
                out.append(Event(i, "assistant", "tool_call", _as_text(inp), b.get("name", ""), inp))
            elif bt == "tool_result":
                out.append(Event(i, "tool", "tool_result", _text_of(b.get("content"))))
    return out


_CODEX_NOISE = ("<environment_context", "<user_instructions", "<permissions", "# AGENTS.md")


def _parse_codex(lines: List[str]) -> List[Event]:
    out: List[Event] = []
    for i, line in enumerate(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "response_item":
            continue
        p = d.get("payload") or {}
        pt = p.get("type")
        if pt == "message" and p.get("role") in ("user", "assistant"):
            text = _text_of(p.get("content"))
            if text.strip() and not text.lstrip().startswith(_CODEX_NOISE):
                out.append(Event(i, p["role"], "text", text))
        elif pt == "reasoning":
            text = "\n".join(s.get("text", "") for s in p.get("summary") or [])
            if text.strip():
                out.append(Event(i, "assistant", "thinking", text))
        elif pt in ("function_call", "custom_tool_call", "local_shell_call"):
            raw = p.get("arguments", p.get("input", p.get("action")))
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    pass
            out.append(Event(i, "assistant", "tool_call", _as_text(raw), p.get("name", pt), raw))
        elif pt in ("function_call_output", "custom_tool_call_output"):
            o = p.get("output")
            if isinstance(o, str) and o.startswith('{"output"'):  # shell results: JSON with output + metadata
                try:
                    o = json.loads(o)
                except ValueError:
                    pass
            if isinstance(o, dict) and "output" in o:
                o = o["output"]
            out.append(Event(i, "tool", "tool_result", _as_text(o)))
    return out


_INJECTED = ("<system-reminder>", "<command-", "<local-command", "<external_", "<environment_context",
             "<user_instructions", "<permissions", "Caveat:")


# Harnesses inject context as messages made only of <tag>...</tag> blocks
# (Codex: <recommended_plugins>, <environment_context>). Pasted text is wrapped too,
# but the user sent it.
_BLOCK = re.compile(r"<([A-Za-z_-]+)[^>]*>.*?</\1>", re.S)


def is_prompt(e: Event) -> bool:
    """A user-typed message, not harness-injected context."""
    if e.role != "user" or e.kind != "text" or e.text.lstrip().startswith(_INJECTED):
        return False
    rest = _BLOCK.sub(lambda m: m.group(0) if m.group(1) == "pasted_content" else "", e.text)
    return bool(rest.strip())


def render(events: List[Event], title: str) -> str:
    parts = [f"# {title}\n"]
    for e in events:
        if e.kind == "text":
            parts.append(f"## {'User' if e.role == 'user' else 'Assistant'}\n\n{e.text.strip()}\n")
        elif e.kind == "thinking":
            parts.append(f"### Assistant (thinking)\n\n{clip(e.text.strip(), 6000)}\n")
        elif e.kind == "tool_call":
            parts.append(f"### Tool call: `{e.tool}`\n\n```\n{clip(e.text, 4000)}\n```\n")
        else:
            parts.append(f"### Tool result\n\n```\n{clip(e.text, 2000)}\n```\n")
    return "\n".join(parts)


# --- "which tool call wrote this file" ---------------------------------------

_PATH_KEYS = ("file_path", "path", "notebook_path", "filename")
_NEW_TEXT_KEYS = ("new_string", "content", "new_source")


def _same_file(v: str, root: Path, rel: str) -> bool:
    if v == rel or v.endswith("/" + rel):
        return True
    p = Path(v) if os.path.isabs(v) else root / v
    try:
        return p.resolve() == (root / rel).resolve()
    except OSError:
        return False


def edit_of(e: Event, root: Path, rel: str) -> Optional[tuple]:
    """If `e` is a tool call touching `rel`, return (strength, text it wrote)."""
    if e.kind != "tool_call":
        return None
    inp = e.input
    if isinstance(inp, dict):
        for k in _PATH_KEYS:
            v = inp.get(k)
            if isinstance(v, str) and _same_file(v, root, rel):
                written = "\n".join(str(inp[x]) for x in _NEW_TEXT_KEYS if inp.get(x))
                return 2, written or e.text
    # Codex apply_patch / shell commands mention the path inside a blob; a patch that
    # adds or updates the file outranks a command that merely mentions it.
    if rel in e.text:
        return (2 if _PATCH.search(e.text) else 1), e.text
    return None


_PATCH = re.compile(r"\*\*\* (Add|Update) File:")


def contains_line(text: str, line: str) -> bool:
    """Is `line` in `text`, ignoring whitespace and JSON escaping (\\" inside patches)?"""
    squash = lambda s: re.sub(r"[\s\\]+", "", s)
    return len(line.strip()) > 3 and squash(line) in squash(text)
