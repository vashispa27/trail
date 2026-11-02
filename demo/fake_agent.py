"""Stand-in for real coding agents in the demo.

Each step edits files in the repo, writes run logs, and appends turns to a transcript
in the exact on-disk format Claude Code / Codex use, so trail picks it up the same way.

usage: fake_agent.py <step> <repo> <claude_dir> <codex_dir>
"""
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

STEP, REPO, CLAUDE_DIR, CODEX_DIR = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3]), Path(sys.argv[4])
ALICE_SID = "7f3c2a10-5b1e-4c55-9d0e-2b8f6a1c9e01"
BOB_SID = "019a4b2c-77d1-7e60-b3a2-5c1d9e8f0a42"


def ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def edit(rel, old, new):
    p = REPO / rel
    p.write_text(p.read_text().replace(old, new))


def write(rel, text):
    p = REPO / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# --- Claude Code format ------------------------------------------------------

def claude_file():
    d = CLAUDE_DIR / re.sub(r"[^A-Za-z0-9-]", "-", str(REPO))
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{ALICE_SID}.jsonl"


def claude(entries):
    with claude_file().open("a") as f:
        for role, content in entries:
            f.write(json.dumps({"type": role, "message": {"role": role, "content": content}, "cwd": str(REPO),
                                "sessionId": ALICE_SID, "gitBranch": "main", "timestamp": ts(),
                                "uuid": str(uuid.uuid4())}) + "\n")


def tool_use(name, inp):
    return {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:12], "name": name, "input": inp}


def tool_result(text):
    return [{"type": "tool_result", "tool_use_id": "toolu_x", "content": text}]


def alice1():
    write("logs/run-17.log", "step 300 loss 2.41 grad_norm 1.2 lr 3.0e-4\nstep 380 loss 2.39 grad_norm 48.7 lr 3.0e-4\n"
                             "step 400 loss nan grad_norm inf\nDIVERGED\n")
    write("logs/run-18.log", "step 400 loss 2.30 grad_norm 2.1 lr 2.0e-4\nstep 520 loss 2.33 grad_norm 31.0 lr 2.0e-4\n"
                             "step 540 loss nan\nDIVERGED\n")
    write("logs/run-19.log", "step 400 loss 2.21 grad_norm 0.8 lr 1.0e-4\nstep 1000 loss 1.79 grad_norm 0.9 lr 9.1e-5\n"
                             "eval_loss 1.82\nDONE\n")
    write("runs/run-19/metrics.json", json.dumps({"run": "run-19", "lr": 1e-4, "warmup": 500, "eval_loss": 1.82,
                                                  "baseline_eval_loss": 2.31}, indent=2) + "\n")
    shared = REPO.parent / "shared-experiments"
    shared.mkdir(exist_ok=True)
    (shared / "lr-sweep.csv").write_text("run,lr,warmup,result\nrun-17,3e-4,100,diverged@400\n"
                                         "run-18,2e-4,100,diverged@540\nrun-19,1e-4,500,eval 1.82\n")
    old_lr, new_lr = "LR = 3e-4", "LR = 1e-4  # 3e-4 / 2e-4 diverged (run-17, run-18)"
    old_wu, new_wu = "WARMUP_STEPS = 100", "WARMUP_STEPS = 500"
    claude([
        ("user", "The 7B LoRA fine-tune keeps blowing up around step 400, logs are in logs/run-17.log. Fix it."),
        ("assistant", [{"type": "thinking", "thinking":
            "run-17: grad_norm jumps from 1.2 to 48.7 at step 380, NaN by 400. Warmup ends at step 100 so we're "
            "at full LR 3e-4 for ~300 steps before it blows up: LR too hot for r=64 LoRA on this data, warmup too "
            "short to settle Adam's second moments. Try 2e-4 first (cheaper change)."},
                       tool_use("Bash", {"command": "python train.py --lr 2e-4 --run run-18",
                                         "description": "Retry with lower LR"})]),
        ("user", tool_result("step 520 loss 2.33 grad_norm 31.0\nstep 540 loss nan\nDIVERGED")),
        ("assistant", [{"type": "thinking", "thinking":
            "2e-4 only delays it (diverges at 540). Not just LR magnitude: short warmup is the bigger issue. "
            "Go to 1e-4 AND warmup 500. Rejected: switching to Adafactor, too big a change for this fix."},
                       tool_use("Bash", {"command": "python train.py --lr 1e-4 --warmup 500 --run run-19",
                                         "description": "Lower LR and longer warmup"})]),
        ("user", tool_result("step 1000 loss 1.79 grad_norm 0.9\neval_loss 1.82\nDONE")),
        ("assistant", [tool_use("Edit", {"file_path": str(REPO / "train.py"), "old_string": old_lr,
                                         "new_string": new_lr})]),
        ("user", tool_result("The file train.py has been updated.")),
        ("assistant", [tool_use("Edit", {"file_path": str(REPO / "train.py"), "old_string": old_wu,
                                         "new_string": new_wu})]),
        ("user", tool_result("The file train.py has been updated.")),
        ("assistant", [{"type": "text", "text":
            "Fixed: LR 3e-4 -> 1e-4 and warmup 100 -> 500. run-19 is stable to step 1000 with eval loss 1.82 "
            "(baseline 2.31). 2e-4 alone still diverged at step 540 (run-18)."}]),
    ])
    edit("train.py", old_lr, new_lr)
    edit("train.py", old_wu, new_wu)


def alice2():
    write("logs/run-20.log", "step 1000 loss 1.78 grad_norm 0.7 clipped 3x\neval_loss 1.81\nDONE\n")
    old, new = "GRAD_CLIP = None", "GRAD_CLIP = 1.0"
    claude([
        ("user", "Add gradient clipping too, as a safety net."),
        ("assistant", [{"type": "thinking", "thinking":
            "run-19 is stable but grad_norm briefly hit 6.0 near step 700. Clip at 1.0 is the usual choice for "
            "LoRA; 0.3 would slow learning (seen in run-12 last week). Verify with run-20."},
                       tool_use("Edit", {"file_path": str(REPO / "train.py"), "old_string": old, "new_string": new})]),
        ("user", tool_result("The file train.py has been updated.")),
        ("assistant", [{"type": "text", "text": "Added clipping at 1.0. run-20: eval loss 1.81, clipping fired 3 times."}]),
    ])
    edit("train.py", old, new)


def alice_leaves():
    # Alice's session ended hours ago, so it is not active when Bob commits.
    old = time.time() - 6 * 3600
    os.utime(claude_file(), (old, old))


# --- Codex format ------------------------------------------------------------

def bob1():
    day = datetime.now()
    d = CODEX_DIR / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"rollout-{day:%Y-%m-%dT%H-%M-%S}-{BOB_SID}.jsonl"
    old = "    key = p\n"
    new = "    key = hashlib.sha1(normalize(p).encode()).hexdigest()\n"
    patch = f"*** Begin Patch\n*** Update File: data.py\n@@\n-{old}+{new}*** End Patch\n"
    items = [
        {"type": "session_meta", "payload": {"id": BOB_SID, "cwd": str(REPO), "originator": "codex_cli"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "Eval numbers look too good. Check if eval prompts leak into train and fix the split."}]}},
        {"type": "response_item", "payload": {"type": "reasoning", "summary": [{"type": "summary_text", "text":
            "Exact-match check finds 3.1% of eval prompts in train. Another 1.4% differ only in whitespace/case, "
            "so dedupe on a normalized hash, not the raw string. Dedupe before splitting, not after."}]}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch", "call_id": "c1",
                                              "input": patch}},
        {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "c1",
                                              "output": "Success. Updated data.py"}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "Dedupe now keys on sha1 of the normalized prompt. Overlap 4.5% -> 0%. "
                                            "Expect eval loss to rise ~0.05; that's the leak going away."}]}},
    ]
    with f.open("w") as out:
        for it in items:
            out.write(json.dumps({"timestamp": ts(), **it}) + "\n")
    write("logs/dedupe-report.txt", "eval prompts: 2000\nexact overlap: 62 (3.1%)\nnormalized overlap: 90 (4.5%)\n"
                                    "after fix: 0\n")
    edit("data.py", old, new)
    edit("data.py", "import json\n", "import hashlib\nimport json\n")


{"alice1": alice1, "alice2": alice2, "alice_leaves": alice_leaves, "bob1": bob1}[STEP]()
