"""Build the demo store the hosted dashboard ships with: three made-up repos, three people,
Claude Code and Codex sessions, all recorded by the real trail hooks.

usage: python3 demo/make_demo_store.py [out_dir]     (default: web/demo-store)

Repos are built in a temp folder with sandboxed ~/.claude and ~/.codex; commit dates are
spread over the last two weeks. Local paths are scrubbed from the output.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRAIL = HERE.parent / "bin" / "trail"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else HERE.parent / "web" / "demo-store").resolve()
SB = Path(tempfile.mkdtemp(prefix="trail-demo-")).resolve()
CLAUDE_DIR, CODEX_DIR = SB / "claude-projects", SB / "codex-sessions"
FAKE_HOME = "/home/dev/code"
NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

PEOPLE = {
    "maya": ("Maya Chen", "maya@acme.dev"),
    "leo": ("Leo Park", "leo@acme.dev"),
    "sam": ("Sam Rivera", "sam@acme.dev"),
}

ENV = {**os.environ, "TRAIL_CLAUDE_DIR": str(CLAUDE_DIR), "TRAIL_CODEX_DIR": str(CODEX_DIR),
       "TRAIL_CACHE": str(SB / "cache")}
ENV.pop("CLAUDE_CODE_SESSION_ID", None)


def ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def age_transcripts() -> None:
    """Sessions that are done should not look active to the next commit."""
    old = time.time() - 6 * 3600
    for f in list(CLAUDE_DIR.rglob("*.jsonl")) + list(CODEX_DIR.rglob("*.jsonl")):
        os.utime(f, (old, old))


class Repo:
    def __init__(self, name: str, files: dict, artifacts: list, owner: str, when: datetime):
        self.name, self.path = name, SB / name
        self.path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", f"git@github.com:acme/{name}.git")
        for rel, text in files.items():
            self.write(rel, text)
        (self.path / ".gitignore").write_text("logs/\nruns/\nreports/\n")
        (self.path / ".trail.yaml").write_text(
            f"store: {OUT}\nrepo: {name}\nharnesses: [claude, codex]\n"
            f"artifacts: {json.dumps(artifacts)}\n")
        self.as_user(owner)
        subprocess.run([str(TRAIL), "init"], cwd=self.path, env=ENV, check=True, capture_output=True)
        self.commit(owner, "Initial commit", when)

    def git(self, *args: str, env=None) -> str:
        return subprocess.run(["git", *args], cwd=self.path, env=env or ENV, check=True,
                              capture_output=True, text=True).stdout

    def as_user(self, who: str) -> None:
        name, email = PEOPLE[who]
        self.git("config", "user.name", name)
        self.git("config", "user.email", email)

    def write(self, rel: str, text: str) -> None:
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def edit(self, rel: str, old: str, new: str) -> None:
        p = self.path / rel
        text = p.read_text()
        assert old in text, f"{rel}: {old!r} not found"
        p.write_text(text.replace(old, new, 1))

    def commit(self, who: str, message: str, when: datetime, claude_sid: str = "") -> None:
        self.as_user(who)
        self.git("add", "-A")
        stamp = when.isoformat()
        env = {**ENV, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        if claude_sid:
            env["CLAUDE_CODE_SESSION_ID"] = claude_sid
        self.git("commit", "-q", "-m", message, env=env)
        age_transcripts()


class Claude:
    """Appends turns in Claude Code's on-disk format; edits apply to the repo too."""

    def __init__(self, repo: Repo):
        self.repo, self.sid = repo, str(uuid.uuid4())
        d = CLAUDE_DIR / re.sub(r"[^A-Za-z0-9-]", "-", str(repo.path))
        d.mkdir(parents=True, exist_ok=True)
        self.file = d / f"{self.sid}.jsonl"

    def _line(self, role: str, content) -> None:
        with self.file.open("a") as f:
            f.write(json.dumps({"type": role, "message": {"role": role, "content": content},
                                "cwd": str(self.repo.path), "sessionId": self.sid, "gitBranch": "main",
                                "timestamp": ts(), "uuid": str(uuid.uuid4())}) + "\n")

    def _tool(self, name: str, inp: dict, result: str) -> None:
        tid = "toolu_" + uuid.uuid4().hex[:20]
        self._line("assistant", [{"type": "tool_use", "id": tid, "name": name, "input": inp}])
        self._line("user", [{"type": "tool_result", "tool_use_id": tid, "content": result}])

    def user(self, text: str) -> "Claude":
        self._line("user", text)
        return self

    def think(self, text: str) -> "Claude":
        self._line("assistant", [{"type": "thinking", "thinking": text}])
        return self

    def say(self, text: str) -> "Claude":
        self._line("assistant", [{"type": "text", "text": text}])
        return self

    def bash(self, command: str, output: str, description: str = "") -> "Claude":
        self._tool("Bash", {"command": command, "description": description}, output)
        return self

    def read(self, rel: str) -> "Claude":
        text = (self.repo.path / rel).read_text()
        numbered = "\n".join(f"{i:>6}\t{l}" for i, l in enumerate(text.splitlines(), 1))
        self._tool("Read", {"file_path": str(self.repo.path / rel)}, numbered)
        return self

    def edit(self, rel: str, old: str, new: str) -> "Claude":
        self.repo.edit(rel, old, new)
        self._tool("Edit", {"file_path": str(self.repo.path / rel), "old_string": old, "new_string": new},
                   f"The file {rel} has been updated.")
        return self

    def write(self, rel: str, text: str) -> "Claude":
        self.repo.write(rel, text)
        self._tool("Write", {"file_path": str(self.repo.path / rel), "content": text},
                   f"File created successfully at: {rel}")
        return self

    def commit(self, who: str, message: str, when: datetime) -> "Claude":
        """Claude runs `git commit` itself, so the hook sees CLAUDE_CODE_SESSION_ID."""
        tid = "toolu_" + uuid.uuid4().hex[:20]
        self._line("assistant", [{"type": "tool_use", "id": tid, "name": "Bash",
                                  "input": {"command": f'git commit -am "{message}"', "description": "Commit"}}])
        self.repo.commit(who, message, when, claude_sid=self.sid)
        self._line("user", [{"type": "tool_result", "tool_use_id": tid,
                             "content": f"[main {self.repo.git('rev-parse', '--short', 'HEAD').strip()}] {message}"}])
        age_transcripts()
        return self


class Codex:
    """Appends items in Codex's rollout format; patches apply to the repo too."""

    def __init__(self, repo: Repo):
        self.repo, self.sid = repo, str(uuid.uuid4())
        day = datetime.now()
        d = CODEX_DIR / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
        d.mkdir(parents=True, exist_ok=True)
        self.file = d / f"rollout-{day:%Y-%m-%dT%H-%M-%S}-{self.sid}.jsonl"
        self._item({"type": "session_meta", "payload": {"id": self.sid, "cwd": str(repo.path),
                                                        "originator": "codex_cli", "cli_version": "0.58.0"}})

    def _item(self, item: dict) -> None:
        with self.file.open("a") as f:
            f.write(json.dumps({"timestamp": ts(), **item}) + "\n")

    def _resp(self, payload: dict) -> None:
        self._item({"type": "response_item", "payload": payload})

    def user(self, text: str) -> "Codex":
        self._resp({"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]})
        return self

    def think(self, text: str) -> "Codex":
        self._resp({"type": "reasoning", "summary": [{"type": "summary_text", "text": text}]})
        return self

    def say(self, text: str) -> "Codex":
        self._resp({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})
        return self

    def shell(self, command: str, output: str) -> "Codex":
        cid = "call_" + uuid.uuid4().hex[:16]
        self._resp({"type": "function_call", "name": "shell", "call_id": cid,
                    "arguments": json.dumps({"command": ["bash", "-lc", command]})})
        self._resp({"type": "function_call_output", "call_id": cid,
                    "output": json.dumps({"output": output, "metadata": {"exit_code": 0}})})
        return self

    def patch(self, rel: str, old: str, new: str) -> "Codex":
        self.repo.edit(rel, old, new)
        minus = "".join(f"-{l}\n" for l in old.splitlines())
        plus = "".join(f"+{l}\n" for l in new.splitlines())
        return self._patch(f"*** Update File: {rel}\n@@\n{minus}{plus}", f"Success. Updated {rel}")

    def add(self, rel: str, text: str) -> "Codex":
        self.repo.write(rel, text)
        body = "".join(f"+{l}\n" for l in text.splitlines())
        return self._patch(f"*** Add File: {rel}\n{body}", f"Success. Added {rel}")

    def _patch(self, body: str, result: str) -> "Codex":
        cid = "call_" + uuid.uuid4().hex[:16]
        self._resp({"type": "custom_tool_call", "name": "apply_patch", "call_id": cid,
                    "input": f"*** Begin Patch\n{body}*** End Patch\n"})
        self._resp({"type": "custom_tool_call_output", "call_id": cid, "output": result})
        return self


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


# --- payments-api --------------------------------------------------------------

def payments_api() -> None:
    r = Repo("payments-api", {
        "README.md": "# payments-api\n\nOrders, charges and refunds for the Acme store. FastAPI + Postgres + Stripe.\n",
        "requirements.txt": "fastapi==0.115.0\nstripe==9.1.0\npsycopg[binary]==3.2.1\n",
        "app/webhooks.py": (
            "from app.db import db\n"
            "from app.stripe import capture\n\n\n"
            "def handle_payment_succeeded(event):\n"
            "    order = db.orders.get(event[\"data\"][\"order_id\"])\n"
            "    capture(order.payment_intent)\n"
            "    order.status = \"paid\"\n"
            "    db.orders.save(order)\n"),
        "app/refunds.py": (
            "from app.db import db\n"
            "from app.stripe import refund\n\n\n"
            "def create_refund(order_id, amount, agent):\n"
            "    order = db.orders.get(order_id)\n"
            "    refund(order.payment_intent, amount)\n"
            "    db.refunds.insert(order_id=order_id, amount=amount, agent=agent)\n"
            "    return {\"ok\": True}\n"),
    }, ["logs/", "reports/*.md"], "sam", ago(13))

    r.write("logs/incident-2291.log",
            "14:02:11 webhook payment_intent.succeeded evt_3Px order=88412 -> captured\n"
            "14:02:41 webhook payment_intent.succeeded evt_3Px order=88412 -> captured   (Stripe retry, 30s)\n"
            "14:02:41 WARN order 88412 captured twice, customer charged $142.00 x2\n"
            "14:05:09 webhook payment_intent.succeeded evt_3Q1 order=88419 -> captured\n"
            "14:05:39 webhook payment_intent.succeeded evt_3Q1 order=88419 -> captured   (Stripe retry, 30s)\n"
            "14:05:39 WARN order 88419 captured twice, customer charged $58.50 x2\n"
            "root cause: handler took 31s (slow capture), Stripe timed out at 30s and retried\n")
    c = Claude(r)
    c.user("Customers are getting charged twice when Stripe retries the payment webhook. "
           "The incident log is logs/incident-2291.log. Fix it so a retry can never double charge.")
    c.bash("grep -c 'captured twice' logs/incident-2291.log", "2", "Count double captures")
    c.read("app/webhooks.py")
    c.think("Both incidents: Stripe retried after 30s because the handler was slow, and the handler has no memory "
            "of events it already processed, so the retry captures again. Two layers needed: (1) skip events we've "
            "seen, keyed by Stripe's event id, (2) skip orders that are already paid. Checking order.status alone "
            "races if two deliveries run at once, so record the event id inside the same transaction.")
    c.edit("app/webhooks.py",
           "def handle_payment_succeeded(event):\n"
           "    order = db.orders.get(event[\"data\"][\"order_id\"])\n"
           "    capture(order.payment_intent)\n",
           "def handle_payment_succeeded(event):\n"
           "    # Stripe retries any delivery that takes over 30s; the same event can arrive twice.\n"
           "    with db.transaction():\n"
           "        if not db.processed_events.add(event[\"id\"]):\n"
           "            return  # already handled\n"
           "        order = db.orders.get(event[\"data\"][\"order_id\"], for_update=True)\n"
           "        if order.status == \"paid\":\n"
           "            return\n"
           "        capture(order.payment_intent)\n")
    c.write("tests/test_webhooks.py",
            "from app.webhooks import handle_payment_succeeded\n\n\n"
            "def test_retry_does_not_capture_twice(fake_db, fake_stripe):\n"
            "    event = {\"id\": \"evt_1\", \"data\": {\"order_id\": 1}}\n"
            "    handle_payment_succeeded(event)\n"
            "    handle_payment_succeeded(event)\n"
            "    assert fake_stripe.captures == 1\n")
    c.bash("pytest tests/test_webhooks.py -q", "1 passed in 0.21s", "Run webhook tests")
    c.say("Fixed. The handler now records Stripe's event id in a `processed_events` table inside the same "
          "transaction as the capture, and skips orders that are already paid. A retried delivery returns early. "
          "Added a test that delivers the same event twice and checks there is one capture.")
    c.commit("maya", "Make payment webhook idempotent", ago(9))

    c.user("Also make this impossible at the database level, in case someone adds another code path.")
    c.write("migrations/0007_processed_events.sql",
            "CREATE TABLE processed_events (\n"
            "    event_id text PRIMARY KEY,\n"
            "    processed_at timestamptz NOT NULL DEFAULT now()\n"
            ");\n\n"
            "-- one successful capture per order, whatever calls it\n"
            "CREATE UNIQUE INDEX captures_one_per_order ON captures (order_id) WHERE status = 'succeeded';\n")
    c.say("Added migration 0007: `processed_events` keyed by event id, and a partial unique index so an order "
          "can only ever have one succeeded capture.")
    c.commit("maya", "Add unique constraints for webhook events and captures", ago(9) + timedelta(minutes=40))

    r.write("reports/refund-abuse.md",
            "# Refund double-clicks, last 30 days\n\n"
            "- 41 orders refunded twice within 10 seconds\n"
            "- all from the support console, same agent, same amount\n"
            "- $3,118 refunded in error\n")
    x = Codex(r)
    x.user("Support agents keep double-clicking refund and we refund twice (see reports/refund-abuse.md). "
           "Limit refunds to 3 per order per hour and reject exact duplicates within a minute.")
    x.shell("rg -n 'def create_refund' app", "app/refunds.py:5:def create_refund(order_id, amount, agent):")
    x.think("Duplicates happen within seconds, same amount and agent. A per-order limit alone would still let the "
            "second click through, so check for an identical refund in the last 60s first, then the hourly cap. "
            "Count from the refunds table instead of an in-memory limiter: there are 4 API replicas.")
    x.patch("app/refunds.py",
            "def create_refund(order_id, amount, agent):\n"
            "    order = db.orders.get(order_id)\n",
            "MAX_PER_HOUR = 3\n\n\n"
            "class RefundRejected(Exception):\n"
            "    pass\n\n\n"
            "def create_refund(order_id, amount, agent):\n"
            "    if db.refunds.count(order_id=order_id, amount=amount, since_seconds=60):\n"
            "        raise RefundRejected(\"duplicate refund within a minute\")\n"
            "    if db.refunds.count(order_id=order_id, since_seconds=3600) >= MAX_PER_HOUR:\n"
            "        raise RefundRejected(\"refund limit reached for this order\")\n"
            "    order = db.orders.get(order_id)\n")
    x.shell("pytest -q tests", "6 passed in 0.48s")
    x.say("Refunds now reject an identical refund within 60s and cap each order at 3 refunds per hour. "
          "Counts come from the refunds table, so the limit holds across all API replicas.")
    r.commit("leo", "Reject duplicate refunds and cap refunds per order", ago(5))

    r.edit("requirements.txt", "stripe==9.1.0", "stripe==9.2.0")
    r.commit("sam", "Bump stripe to 9.2.0", ago(2))


# --- web-app -------------------------------------------------------------------

def web_app() -> None:
    r = Repo("web-app", {
        "README.md": "# web-app\n\nThe Acme storefront. Next.js, TypeScript.\n",
        "package.json": json.dumps({"name": "web-app", "private": True,
                                    "scripts": {"dev": "next dev", "test:e2e": "playwright test"}}, indent=2) + "\n",
        "src/components/CheckoutButton.tsx": (
            "export function CheckoutButton({ cart }: { cart: Cart }) {\n"
            "  const [loading, setLoading] = useState(false);\n\n"
            "  async function submit() {\n"
            "    setLoading(true);\n"
            "    await placeOrder(cart);\n"
            "    setLoading(false);\n"
            "  }\n\n"
            "  return <button onClick={submit}>{loading ? <Spinner /> : \"Place order\"}</button>;\n"
            "}\n"),
        "src/theme.ts": "export const theme = {\n  bg: \"#ffffff\",\n  text: \"#111111\",\n};\n",
        "e2e/checkout.spec.ts": (
            "test(\"checkout\", async ({ page }) => {\n"
            "  await page.goto(\"/cart\");\n"
            "  await page.click(\"text=Place order\");\n"
            "  await page.waitForTimeout(500);\n"
            "  await expect(page.locator(\"h1\")).toHaveText(\"Thanks for your order\");\n"
            "});\n"),
    }, ["logs/"], "leo", ago(14))

    c = Claude(r)
    c.user("On slow 3G the checkout button flickers and some people manage to place the order twice. Fix it.")
    c.read("src/components/CheckoutButton.tsx")
    c.think("The button is never disabled, so a second tap during the request fires submit again. The flicker is "
            "the label swapping to a spinner, which changes the button width. Disable while pending, guard with a "
            "ref (state updates are async, two fast taps both see loading=false), and keep the width fixed.")
    c.edit("src/components/CheckoutButton.tsx",
           "  const [loading, setLoading] = useState(false);\n\n"
           "  async function submit() {\n"
           "    setLoading(true);\n"
           "    await placeOrder(cart);\n"
           "    setLoading(false);\n"
           "  }\n\n"
           "  return <button onClick={submit}>{loading ? <Spinner /> : \"Place order\"}</button>;\n",
           "  const [loading, setLoading] = useState(false);\n"
           "  const inFlight = useRef(false); // two quick taps both see loading=false\n\n"
           "  async function submit() {\n"
           "    if (inFlight.current) return;\n"
           "    inFlight.current = true;\n"
           "    setLoading(true);\n"
           "    try {\n"
           "      await placeOrder(cart);\n"
           "    } finally {\n"
           "      inFlight.current = false;\n"
           "      setLoading(false);\n"
           "    }\n"
           "  }\n\n"
           "  return (\n"
           "    <button onClick={submit} disabled={loading} aria-busy={loading} style={{ minWidth: 140 }}>\n"
           "      {loading ? <Spinner /> : \"Place order\"}\n"
           "    </button>\n"
           "  );\n")
    c.bash("npx tsc --noEmit", "", "Type check")
    c.say("The button is disabled while the order is pending, a ref blocks a second tap that lands before the "
          "re-render, and a fixed min-width stops the flicker when the label swaps to the spinner.")
    c.commit("leo", "Disable checkout button while the order is pending", ago(7))

    c = Claude(r)
    c.user("Add a dark mode toggle in the header. It should follow the system setting until someone picks, "
           "then remember their choice.")
    c.think("Three states, not two: system, light, dark. Store only an explicit pick in localStorage; with no "
            "pick, follow prefers-color-scheme. Set data-theme on <html> so CSS variables switch.")
    c.edit("src/theme.ts", "export const theme = {\n  bg: \"#ffffff\",\n  text: \"#111111\",\n};\n",
           "export const themes = {\n"
           "  light: { bg: \"#ffffff\", text: \"#111111\" },\n"
           "  dark: { bg: \"#0d1117\", text: \"#e6edf3\" },\n"
           "};\n\n"
           "export type ThemeName = keyof typeof themes;\n")
    c.write("src/components/ThemeToggle.tsx",
            "export function ThemeToggle() {\n"
            "  const [pick, setPick] = useState<ThemeName | null>(() => localStorage.getItem(\"theme\") as ThemeName | null);\n\n"
            "  useEffect(() => {\n"
            "    if (pick) document.documentElement.dataset.theme = pick;\n"
            "    else delete document.documentElement.dataset.theme; // follow the system\n"
            "  }, [pick]);\n\n"
            "  function toggle() {\n"
            "    const dark = pick ? pick === \"dark\" : matchMedia(\"(prefers-color-scheme: dark)\").matches;\n"
            "    const next = dark ? \"light\" : \"dark\";\n"
            "    localStorage.setItem(\"theme\", next);\n"
            "    setPick(next);\n"
            "  }\n\n"
            "  return <button onClick={toggle} aria-label=\"Toggle dark mode\">◐</button>;\n"
            "}\n")
    c.say("Added `ThemeToggle`. With no saved choice it follows the system setting; clicking saves an explicit "
          "light or dark choice in localStorage and sets `data-theme` on the root element.")
    c.commit("sam", "Add dark mode toggle", ago(4))

    r.write("logs/ci-flake-runs.txt",
            "run 4411  checkout  PASS  order api 210ms\n"
            "run 4412  checkout  FAIL  order api 640ms  expected 'Thanks for your order', got 'Placing order…'\n"
            "run 4413  checkout  PASS  order api 180ms\n"
            "run 4414  checkout  PASS  order api 330ms\n"
            "run 4415  checkout  FAIL  order api 710ms  expected 'Thanks for your order', got 'Placing order…'\n"
            "failures: 2/5, all with order api > 500ms\n")
    x = Codex(r)
    x.user("The checkout e2e test fails on CI about 1 run in 5. Figure out why and make it reliable.")
    x.shell("cat logs/ci-flake-runs.txt | grep FAIL",
            "run 4412  checkout  FAIL  order api 640ms ...\nrun 4415  checkout  FAIL  order api 710ms ...")
    x.think("Every failure has the order API slower than 500ms, and the test sleeps a fixed 500ms before checking "
            "the heading. Waiting for the actual /api/orders response removes the race; a longer sleep would just "
            "move the threshold.")
    x.patch("e2e/checkout.spec.ts",
            "  await page.click(\"text=Place order\");\n"
            "  await page.waitForTimeout(500);\n",
            "  const order = page.waitForResponse((r) => r.url().endsWith(\"/api/orders\") && r.ok());\n"
            "  await page.click(\"text=Place order\");\n"
            "  await order; // a fixed 500ms sleep failed whenever the API took longer\n")
    x.shell("npx playwright test e2e/checkout.spec.ts --repeat-each 30", "30 passed (41.2s)")
    x.say("The test slept 500ms and failed whenever the order API was slower than that (both CI failures were "
          "640ms and 710ms). It now waits for the /api/orders response. 30 repeated runs pass.")
    r.commit("maya", "Wait for the order response in checkout e2e instead of sleeping", ago(1))


# --- ml-pipeline ---------------------------------------------------------------

def ml_pipeline() -> None:
    r = Repo("ml-pipeline", {
        "README.md": "# ml-pipeline\n\nFine-tuning for the support assistant. LoRA on a 7B base model.\n",
        "train.py": "MODEL = \"llama-7b\"\nLORA_RANK = 64\nLR = 3e-4\nWARMUP_STEPS = 100\nGRAD_CLIP = None\n"
                    "EARLY_STOP_PATIENCE = None\n",
        "data.py": "import json\n\n\ndef split(prompts, eval_frac=0.05):\n    seen = set()\n    for p in prompts:\n"
                   "        key = p\n        if key in seen:\n            continue\n        seen.add(key)\n",
    }, ["logs/", "runs/**/metrics.json"], "maya", ago(15))

    r.write("logs/run-17.log", "step 300 loss 2.41 grad_norm 1.2 lr 3.0e-4\nstep 380 loss 2.39 grad_norm 48.7\n"
                               "step 400 loss nan grad_norm inf\nDIVERGED\n")
    r.write("logs/run-18.log", "step 400 loss 2.30 grad_norm 2.1 lr 2.0e-4\nstep 520 loss 2.33 grad_norm 31.0\n"
                               "step 540 loss nan\nDIVERGED\n")
    r.write("logs/run-19.log", "step 400 loss 2.21 grad_norm 0.8 lr 1.0e-4\nstep 1000 loss 1.79 grad_norm 0.9\n"
                               "eval_loss 1.82\nDONE\n")
    r.write("runs/run-19/metrics.json", json.dumps({"run": "run-19", "lr": 1e-4, "warmup": 500, "eval_loss": 1.82,
                                                    "baseline_eval_loss": 2.31}, indent=2) + "\n")
    c = Claude(r)
    c.user("The 7B LoRA fine-tune keeps blowing up around step 400. Logs are in logs/run-17.log. Fix it.")
    c.think("run-17: grad_norm jumps from 1.2 to 48.7 at step 380, NaN by 400. Warmup ends at step 100, so we're at "
            "full LR 3e-4 for ~300 steps before it blows up. LR too hot for r=64 LoRA on this data, and warmup too "
            "short. Try 2e-4 first, it's the smaller change.")
    c.bash("python train.py --lr 2e-4 --run run-18", "step 520 loss 2.33 grad_norm 31.0\nstep 540 loss nan\nDIVERGED",
           "Retry with lower LR")
    c.think("2e-4 only delays it (diverges at 540). The short warmup is the bigger issue. Go to 1e-4 AND warmup "
            "500. Rejected: switching to Adafactor, too big a change for this fix.")
    c.bash("python train.py --lr 1e-4 --warmup 500 --run run-19", "step 1000 loss 1.79 grad_norm 0.9\neval_loss 1.82\nDONE",
           "Lower LR and longer warmup")
    c.edit("train.py", "LR = 3e-4", "LR = 1e-4  # 3e-4 and 2e-4 diverged (run-17, run-18)")
    c.edit("train.py", "WARMUP_STEPS = 100", "WARMUP_STEPS = 500")
    c.say("Fixed: LR 3e-4 to 1e-4 and warmup 100 to 500. run-19 is stable to step 1000 with eval loss 1.82 "
          "(baseline 2.31). 2e-4 alone still diverged at step 540 (run-18).")
    c.commit("sam", "Lower LR and lengthen warmup to stop divergence", ago(6))

    r.write("logs/run-20.log", "step 1000 loss 1.78 grad_norm 0.7 clipped 3x\neval_loss 1.81\nDONE\n")
    c.user("Add gradient clipping too, as a safety net.")
    c.think("run-19 is stable but grad_norm briefly hit 6.0 near step 700. Clip at 1.0 is the usual choice for "
            "LoRA; 0.3 slowed learning in run-12 last week.")
    c.edit("train.py", "GRAD_CLIP = None", "GRAD_CLIP = 1.0")
    c.bash("python train.py --run run-20", "step 1000 loss 1.78 grad_norm 0.7 clipped 3x\neval_loss 1.81\nDONE")
    c.say("Added clipping at 1.0. run-20: eval loss 1.81, clipping fired 3 times.")
    c.commit("sam", "Clip gradients at 1.0", ago(6) + timedelta(minutes=35))

    r.write("logs/dedupe-report.txt", "eval prompts: 2000\nexact overlap: 62 (3.1%)\nnormalized overlap: 90 (4.5%)\n"
                                      "after fix: 0\n")
    x = Codex(r)
    x.user("Eval numbers look too good. Check whether eval prompts leak into train and fix the split.")
    x.shell("python -m scripts.overlap --eval data/eval.jsonl --train data/train.jsonl",
            "exact overlap: 62 / 2000 (3.1%)\nnormalized overlap: 90 / 2000 (4.5%)")
    x.think("Exact match finds 3.1% of eval prompts in train; another 1.4% differ only in whitespace or case. "
            "Dedupe on a hash of the normalized prompt, not the raw string, and dedupe before splitting.")
    x.patch("data.py", "        key = p\n", "        key = hashlib.sha1(normalize(p).encode()).hexdigest()\n")
    x.patch("data.py", "import json\n", "import hashlib\nimport json\n")
    x.say("Dedupe now keys on the sha1 of the normalized prompt. Overlap went from 4.5% to 0%. Expect eval loss "
          "to rise about 0.05; that is the leak going away.")
    r.commit("maya", "Dedupe eval prompts by normalized hash", ago(3))

    r.write("runs/run-23/metrics.json", json.dumps({"run": "run-23", "stopped_at_step": 2600, "best_step": 2000,
                                                    "eval_loss": 1.84}, indent=2) + "\n")
    c = Claude(r)
    c.user("Runs keep going long after eval loss stops improving. Add early stopping.")
    c.think("Eval runs every 200 steps. Patience 3 evals = 600 steps without improvement, enough to ride out "
            "noise (eval loss wobbles about 0.01). Keep the best checkpoint, not the last one.")
    c.edit("train.py", "EARLY_STOP_PATIENCE = None", "EARLY_STOP_PATIENCE = 3  # evals (every 200 steps) without a new best")
    c.bash("python train.py --run run-23", "eval 2000 loss 1.84 (best)\neval 2200 loss 1.85\neval 2400 loss 1.86\n"
           "eval 2600 loss 1.85\nearly stop at 2600, restoring step 2000")
    c.say("Early stopping with patience 3 evals. run-23 stopped at step 2600 and restored the step-2000 "
          "checkpoint (eval loss 1.84), saving about 40% of the compute of a full run.")
    c.commit("leo", "Stop training early when eval loss plateaus", ago(0.3))


def scrub() -> None:
    """Replace sandbox paths, make session timestamps match the commit dates."""
    enc = re.sub(r"[^A-Za-z0-9-]", "-", str(SB))
    for f in OUT.rglob("*"):
        if not f.is_file():
            continue
        text = f.read_text(errors="replace")
        new = text.replace(str(OUT), "supabase://trail/main").replace(str(SB), FAKE_HOME).replace(enc, re.sub(r"[^A-Za-z0-9-]", "-", FAKE_HOME))
        if f.name == "meta.json":
            meta = json.loads(new)
            meta["last_seen"] = max(c["date"] for c in meta["commits"])
            new = json.dumps(meta, indent=2) + "\n"
        if f.name == "repo.json":
            info = json.loads(new)  # made-up remotes: show them, don't link them
            new = json.dumps({**info, "github": None, "demo": True}, indent=2) + "\n"
        if new != text:
            f.write_text(new)
    for f in OUT.rglob(".trail-sync.json"):
        f.unlink()


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    try:
        payments_api()
        web_app()
        ml_pipeline()
        scrub()
    finally:
        shutil.rmtree(SB, ignore_errors=True)
    n = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"demo store: {n} files in {OUT}")


if __name__ == "__main__":
    main()
