# trail

The why behind every commit. trail links each git commit to the AI agent sessions that wrote it (Claude Code, Codex), plus the logs and files you choose.

## Why we built this

Agents now write a lot of our code. The thinking behind that code (the prompt, the dead ends, the logs the agent read, the runs it compared) lives in a chat window. A week later the chat is gone. Months later, `git blame` points at a commit that says "fix webhook", and nobody knows why the line is there.

## The problem

- Code review shows what changed, not why.
- Agent conversations are not saved next to the code they produced.
- Logs and experiment results that justified a change get lost.
- No one can answer "why is this line like this?" once the author moves on, or when the author was an agent.

## The solution

trail installs two git hooks. When you commit, it:

1. Finds the Claude Code or Codex session that edited the staged files.
2. Adds a `Trail-Session` line (and a `Trail-Link` to the dashboard) to the commit message.
3. Saves the conversation, the diff and your chosen logs or artifacts to a store: Supabase Storage, S3 or a local folder.

Then `trail why file:line` goes from the line to the commit, to the session, to the exact prompt and reasoning. A GitHub-style dashboard lets you browse it all.

## Setup

Needs Python 3.9+ and git. The dashboard needs Node.js 20+.

```sh
git clone https://github.com/blurr2710/trail
cd your-repo
/path/to/trail/bin/trail init     # writes .trail.yaml and installs the git hooks
git commit ...                    # sessions are linked automatically from now on
```

Choose where traces go in `.trail.yaml`:

```yaml
store: supabase://trail/main   # or s3://bucket/prefix, or a local folder like ~/.trail/store
artifacts:                     # files kept with each commit
  - logs/
  - runs/**/metrics.json
```

For Supabase, put the keys in `~/.trail/credentials` (never in `.trail.yaml`):

```sh
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
```

Try it without a real repo: `sh demo/run_demo.sh` builds a throwaway repo, fakes two agent sessions, commits, and runs the commands below.

## Commands

| command | what it does |
|---|---|
| `trail init` | write `.trail.yaml`, install the git hooks |
| `trail status` | sessions and files the next commit would link |
| `trail why FILE:LINE` | line to commit to session: prompt, reasoning, edit, artifacts |
| `trail log` | commits in the trail with their sessions |
| `trail show SHA\|SESSION` | everything stored for a commit or session |
| `trail grep PATTERN` | search all transcripts, logs and artifacts |
| `trail capture` | save sessions and artifacts without committing |
| `trail record [REV]` | add an existing commit to the trail |
| `trail pull [PATH] [--all]` | update the local copy of the store |
| `trail push` | upload anything that failed to upload |
| `trail path` | print the local folder of this repo's trail |
| `trail ui [--port 8787]` | open the dashboard over your store |

## Dashboard

`web/` is a Next.js app: a landing page at `/` and a GitHub-style dashboard at `/repos`.

```sh
cd web && npm install && npm run dev      # demo data, http://localhost:3000
trail ui                                  # your own store, http://localhost:8787/repos
```

With no settings it shows `web/demo-store`: three made-up repos and three people, recorded by the real hooks (`python3 demo/make_demo_store.py` rebuilds it). To show a real store, set `TRAIL_STORE` (`supabase://bucket/prefix` or a folder path), plus `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for Supabase.

Deploy on Vercel: import the repo and set the Root Directory to `web`. It works with no environment variables (demo data).
