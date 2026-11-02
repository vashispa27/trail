import Link from "next/link";
import { HashRedirect } from "@/components/hash-redirect";
import { Icon } from "@/components/ui";
import { href } from "@/lib/format";
import { GITHUB } from "@/lib/site";
import { commits } from "@/lib/store";

export const dynamic = "force-dynamic";

/** Link the hero mockup to the real demo session it shows, when the demo store has it. */
async function heroLink() {
  try {
    const c = (await commits("payments-api")).find((x) => x.subject === "Make payment webhook idempotent");
    if (c?.sessions[0]) return { link: href.session("payments-api", c.sessions[0].session_id), sha: c.sha.slice(0, 7) };
  } catch {}
  return { link: "/repos", sha: "a41c9e2" };
}

const Mark = ({ size = 56 }: { size?: number }) => (
  <span className="lp-mark" style={{ width: size, height: size }} aria-hidden="true">
    <svg viewBox="0 0 32 32"><path d="M9 7v13a5 5 0 0 0 5 5h9M9 13h12" /></svg>
  </span>
);

const GithubIcon = () => <Icon name="github" />;

const people = [
  { who: "Maya", c: "#4f8a6e", subject: "Make payment webhook idempotent", meta: "claude · payments-api", on: true },
  { who: "Leo", c: "#d08a3a", subject: "Reject duplicate refunds and cap…", meta: "codex · payments-api" },
  { who: "Sam", c: "#5b6ad0", subject: "Lower LR and lengthen warmup", meta: "claude · ml-pipeline" },
  { who: "Maya", c: "#4f8a6e", subject: "Wait for the order response in…", meta: "codex · web-app" },
  { who: "Leo", c: "#d08a3a", subject: "Stop training early when eval…", meta: "claude · ml-pipeline" },
];

const commands = [
  ["trail init", "Writes .trail.yaml and installs two git hooks. That is the whole setup."],
  ["trail why file:line", "Blame, then the commit, then the session: the prompt, the reasoning and the edit."],
  ["trail log", "Commits in the trail, with the sessions behind each one."],
  ["trail grep pattern", "One search across every transcript, log and artifact."],
  ["trail show sha", "Everything stored for a commit or a session."],
  ["trail ui", "This dashboard, over your own store."],
];

const faqs = [
  ["Do I have to change how I work?",
    "No. Commit like you always do. The hooks find the Claude Code or Codex session that edited the staged files and link it to the commit."],
  ["Where is the data stored?",
    "Wherever you point it: Supabase Storage, any S3-compatible bucket, or a local folder. It is a plain folder tree you can grep."],
  ["What ends up in the commit itself?",
    "Two trailer lines: Trail-Session with the session id and Trail-Link to the dashboard. The transcript stays in your store, not in git."],
  ["Which agents does it support?",
    "Claude Code and Codex today. Each harness is a small parser, so adding another is a short change."],
];

export default async function Landing() {
  const hero = await heroLink();
  return (
    <div className="lp">
      <HashRedirect />
      <header className="lp-nav">
        <Link href="/" className="lp-brand"><Mark size={28} /><span>trail</span></Link>
        <nav>
          <Link href="/repos" className="lp-navlink">Demo</Link>
          <a href={GITHUB} className="lp-pill lp-dark sm" target="_blank" rel="noopener"><GithubIcon />GitHub</a>
        </nav>
      </header>

      <section className="lp-hero">
        <a className="lp-announce rise" href={GITHUB} target="_blank" rel="noopener">
          <b>Open source</b><span>Works with Claude Code and Codex</span><span className="lp-arrow">↗</span>
        </a>
        <h1 className="rise d1">Meet <Mark /> trail</h1>
        <p className="lp-sub rise d2">
          Your agents write the code. trail keeps the conversation that wrote it: the prompt, the reasoning,
          the logs. Linked to every commit, one command away from any line.
        </p>
        <div className="lp-ctas rise d3">
          <Link href="/repos" className="lp-pill lp-dark">See the demo</Link>
          <a href={GITHUB} className="lp-pill lp-light" target="_blank" rel="noopener"><GithubIcon />View on GitHub</a>
        </div>

        <div className="lp-window rise d4">
          <aside>
            <div className="lp-dots"><i /><i /><i /></div>
            <div className="lp-search">Search commits</div>
            {people.map((p, i) => (
              <div key={i} className={`lp-thread${p.on ? " on" : ""}`}>
                <span className="lp-av" style={{ background: p.c }}>{p.who[0]}</span>
                <div><b>{p.subject}</b><small>{p.meta}</small></div>
              </div>
            ))}
          </aside>
          <div className="lp-pane">
            <div className="lp-pane-head">
              <span className="lp-av sm" style={{ background: "#4f8a6e" }}>M</span>
              <b>Make payment webhook idempotent</b>
              <span className="lp-sha">{hero.sha}</span>
            </div>
            <div className="lp-chat">
              <div className="lp-msg you">
                Customers are getting charged twice when Stripe retries the payment webhook. Fix it so a retry can
                never double charge.
              </div>
              <div className="lp-think">
                <span>Thinking</span>
                Stripe retried after 30s because the handler was slow, and the handler has no memory of events it
                already processed. Record the event id inside the same transaction as the capture.
              </div>
              <div className="lp-tool">
                <div className="lp-tool-head"><span>Edit</span>app/webhooks.py</div>
                <pre>
                  <span className="add">{"+    with db.transaction():"}</span>{"\n"}
                  <span className="add">{"+        if not db.processed_events.add(event[\"id\"]):"}</span>{"\n"}
                  <span className="add">{"+            return  # already handled"}</span>
                </pre>
              </div>
              <div className="lp-msg agent">
                Fixed. A retried delivery now returns early, and a test delivers the same event twice and checks
                there is one capture.
              </div>
            </div>
            <div className="lp-compose">
              <code>$ trail why app/webhooks.py:9</code>
              <Link href={hero.link} className="lp-pill lp-dark xs">Open in demo</Link>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-band">
        <div className="lp-band-text">
          <p className="lp-eyebrow">The problem</p>
          <h2>Code review shows what changed. Not why.</h2>
          <p>
            More of your code is written by agents every week. The reasoning behind it, the dead ends, the logs
            it read and the runs it compared, lives in a chat window that is gone by Friday. Six months later
            <code> git blame </code> points at a commit that says &ldquo;fix webhook&rdquo;, and nobody remembers why.
          </p>
        </div>
        <div className="lp-blame" aria-hidden="true">
          <div><span>a41c9e2</span><span>maya</span><code>with db.transaction():</code></div>
          <div><span>a41c9e2</span><span>maya</span><code>if not db.processed_events…</code></div>
          <div className="hl"><span>a41c9e2</span><span>maya</span><code>return  # already handled</code></div>
          <div className="lp-q">why?</div>
        </div>
      </section>

      <section className="lp-section">
        <p className="lp-eyebrow center">The solution</p>
        <h2 className="lp-h2">A trail behind every commit</h2>
        <p className="lp-lead">
          trail links each commit to the agent sessions that produced it, plus the logs and artifacts you choose,
          and stores them as one folder tree per repo.
        </p>
        <div className="lp-grid">
          <div className="lp-card">
            <h3>Hooks, not habits</h3>
            <p>Two git hooks find the session that edited the staged files and link it when you commit.</p>
            <div className="lp-commit">
              <b>Make payment webhook idempotent</b>
              <span>Trail-Session: claude:7c1e…</span>
              <span>Trail-Link: localhost:8787/repos/payments-api/session/7c1e…</span>
            </div>
          </div>
          <div className="lp-card">
            <h3>Ask any line why</h3>
            <p>Blame to commit to session to the exact prompt, reasoning and edit that wrote the line.</p>
            <div className="lp-term">
              <div><i>$</i> trail why train.py:3</div>
              <div className="m">a91f02c Lower LR and lengthen warmup · sam · claude</div>
              <div><b>prompt</b> The 7B LoRA fine-tune keeps blowing up around step 400.</div>
              <div><b>reasoning</b> 2e-4 only delays it. Go to 1e-4 and warmup 500.</div>
              <div><b>artifacts</b> logs/run-17.log, runs/run-19/metrics.json</div>
            </div>
          </div>
          <div className="lp-card">
            <h3>Logs and artifacts ride along</h3>
            <p>Training logs, metrics, CI output, reports. Whatever you list in .trail.yaml is kept with the commit.</p>
            <div className="lp-files">
              {["logs/run-17.log", "runs/run-19/metrics.json", "logs/ci-flake-runs.txt", "reports/refund-abuse.md", "conversation.md"].map((f) => (
                <span key={f}><Icon name="file" />{f}</span>
              ))}
            </div>
          </div>
          <div className="lp-card">
            <h3>Browse it like GitHub</h3>
            <p>Repos as folders, commits with their sessions, every conversation. No auth needed for the demo.</p>
            <Link href="/repos" className="lp-mini">
              <div className="lp-mini-tabs"><span className="on">Code</span><span>Commits <i>5</i></span><span>Sessions <i>3</i></span></div>
              {["payments-api", "web-app", "ml-pipeline"].map((r) => (
                <div key={r} className="lp-mini-row"><Icon name="repo" />{r}<small>Demo</small></div>
              ))}
            </Link>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <h2 className="lp-h2">Works where you already work</h2>
        <div className="lp-chips">
          {["Claude Code", "Codex", "git", "GitHub", "Supabase Storage", "S3", "Local folder"].map((x) => <span key={x}>{x}</span>)}
        </div>
      </section>

      <section className="lp-section">
        <h2 className="lp-h2">Six commands</h2>
        <div className="lp-cmds">
          {commands.map(([c, d]) => (
            <div key={c}><code>{c}</code><p>{d}</p></div>
          ))}
        </div>
      </section>

      <section className="lp-section narrow">
        <h2 className="lp-h2">FAQs</h2>
        {faqs.map(([q, a]) => (
          <details key={q} className="lp-faq">
            <summary>{q}<span>+</span></summary>
            <p>{a}</p>
          </details>
        ))}
      </section>

      <section className="lp-final">
        <Mark size={64} />
        <h2>See the trail behind a commit</h2>
        <p>Three demo repos, three people, Claude Code and Codex sessions.</p>
        <div className="lp-ctas">
          <Link href="/repos" className="lp-pill lp-dark">See the demo</Link>
          <a href={GITHUB} className="lp-pill lp-light" target="_blank" rel="noopener"><GithubIcon />View on GitHub</a>
        </div>
      </section>

      <footer className="lp-foot">
        <span>trail</span>
        <span>Open source. Built as a demo.</span>
        <a href={GITHUB} target="_blank" rel="noopener">GitHub</a>
      </footer>
    </div>
  );
}
