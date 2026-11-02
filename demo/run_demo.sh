#!/bin/sh
# End-to-end demo: two people, two agents (Claude Code + Codex), one repo, one trail.
# Everything lives in demo/.sandbox; your real ~/.claude and ~/.codex are not touched.
#
# Local store by default. To use Supabase Storage instead:
#   TRAIL_DEMO_STORE=supabase://trail-demo/run1 sh demo/run_demo.sh
# with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set (env or ~/.trail/credentials).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
TRAIL="$HERE/../bin/trail"
SB="$HERE/.sandbox"
rm -rf "$SB"
mkdir -p "$SB"

# Point trail at sandboxed harness dirs instead of ~/.claude and ~/.codex.
export TRAIL_CLAUDE_DIR="$SB/claude-projects" TRAIL_CODEX_DIR="$SB/codex-sessions" TRAIL_CACHE="$SB/cache"
STORE="${TRAIL_DEMO_STORE:-$SB/store}"
unset CLAUDE_CODE_SESSION_ID
agent() { python3 "$HERE/fake_agent.py" "$1" "$SB/cortex" "$TRAIL_CLAUDE_DIR" "$TRAIL_CODEX_DIR"; }
say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

say "Create repo 'cortex' and install trail"
mkdir "$SB/cortex" && cd "$SB/cortex"
git init -q -b main
git config user.email alice@cortex.dev && git config user.name Alice
cat > train.py <<'EOF'
MODEL = "llama-7b"
LORA_RANK = 64
LR = 3e-4
WARMUP_STEPS = 100
GRAD_CLIP = None
EOF
cat > data.py <<'EOF'
import json


def split(prompts, eval_frac=0.05):
    seen = set()
    for p in prompts:
        key = p
        seen.add(key)
EOF
printf 'logs/\nruns/\n' > .gitignore
cat > .trail.yaml <<EOF
store: $STORE
repo: cortex
harnesses: [claude, codex]
artifacts:
  - logs/
  - runs/**/metrics.json
  - ../shared-experiments/*.csv
exclude: ["**/*.ckpt"]
EOF
"$TRAIL" init
git add -A && git commit -qm "Initial training config"

say "Alice's Claude Code session fixes the divergence, and Claude commits"
agent alice1
CLAUDE_CODE_SESSION_ID=7f3c2a10-5b1e-4c55-9d0e-2b8f6a1c9e01 sh -c 'git commit -qam "Lower LR and lengthen warmup to stop divergence"'

say "Same session keeps going: adds grad clipping, second commit"
agent alice2
CLAUDE_CODE_SESSION_ID=7f3c2a10-5b1e-4c55-9d0e-2b8f6a1c9e01 sh -c 'git commit -qam "Clip gradients at 1.0"'
agent alice_leaves

say "Bob works in Codex, then commits from his own terminal"
git config user.email bob@cortex.dev && git config user.name Bob
agent bob1
"$TRAIL" status
git commit -qam "Dedupe eval prompts by normalized hash"

say "git log: commits carry a Trail-Session trailer"
git log --format='%h %an: %s%n   %(trailers:key=Trail-Session)' | sed '/^ *$/d'

say "trail log"
"$TRAIL" log

say "trail why train.py:$(grep -n '^LR' train.py | cut -d: -f1)"
"$TRAIL" why "train.py:$(grep -n '^LR' train.py | cut -d: -f1)"

say "trail why train.py:$(grep -n '^GRAD_CLIP' train.py | cut -d: -f1)"
"$TRAIL" why "train.py:$(grep -n '^GRAD_CLIP' train.py | cut -d: -f1)"

say "trail why data.py:$(grep -n 'hashlib.sha1' data.py | cut -d: -f1)"
"$TRAIL" why "data.py:$(grep -n 'hashlib.sha1' data.py | cut -d: -f1)"

say "trail grep diverged   (transcripts + logs + artifacts, one search)"
"$TRAIL" grep -i diverged

case "$STORE" in
  supabase://*|s3://*)
    say "Fresh machine: wipe the local mirror, read everything back from $STORE"
    rm -rf "$TRAIL_CACHE"
    "$TRAIL" log
    "$TRAIL" why "train.py:$(grep -n '^LR' train.py | cut -d: -f1)" | head -8
    "$TRAIL" pull ;;
esac

say "The trail is a folder tree (local mirror of the store)"
cd "$("$TRAIL" path)" && find . -type f | sort
