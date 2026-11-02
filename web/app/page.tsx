import Image from "next/image";
import Link from "next/link";
import { HashRedirect } from "@/components/hash-redirect";
import { LiveDemo } from "@/components/live-demo";
import { Icon } from "@/components/ui";
import { href } from "@/lib/format";
import { GITHUB } from "@/lib/site";
import { commits } from "@/lib/store";
import shotCommit from "@/public/shots/commit.png";
import shotRepos from "@/public/shots/repos.png";
import shotSession from "@/public/shots/session.png";

export const dynamic = "force-dynamic";

/** Link the hero mockup to the real demo session it shows, when the demo store has it. */
async function heroLink() {
  try {
    const c = (await commits("payments-api")).find((x) => x.subject === "Make payment webhook idempotent");
    if (c?.sessions[0]) return { link: href.session("payments-api", c.sessions[0].session_id), commit: href.commit("payments-api", c.sha), sid: c.sessions[0].session_id };
  } catch {}
  return { link: "/repos", commit: "/repos", sid: "7c1e4a90" };
}

const Mark = ({ size = 56 }: { size?: number }) => (
  <span className="lp-mark" style={{ width: size, height: size }} aria-hidden="true">
    <svg viewBox="0 0 32 32"><path d="M9 9h14M16 9v15" /></svg>
  </span>
);

const GithubIcon = () => <Icon name="github" />;

/** A painted backdrop (sky, hills, grain) that UI pieces float on. */
const Scene = ({ tone, className = "", children }: { tone: string; className?: string; children: React.ReactNode }) => (
  <div className={`lp-scene ${tone} ${className}`}>
    <svg className="lp-hills" viewBox="0 0 800 300" preserveAspectRatio="none" aria-hidden="true">
      <path className="far" d="M0 170 C90 120 170 150 250 112 S420 40 520 96 S690 70 800 118 V300 H0Z" />
      <path className="near" d="M0 236 C140 190 250 228 370 200 S600 170 800 214 V300 H0Z" />
    </svg>
    <div className="lp-scene-body">{children}</div>
  </div>
);

const Shot = ({ src, alt, url }: { src: typeof shotSession; alt: string; url: string }) => (
  <div className="lp-browser">
    <div className="lp-browser-bar"><span className="lp-dots"><i /><i /><i /></span><span className="lp-url">{url}</span></div>
    <Image src={src} alt={alt} sizes="(max-width: 900px) 100vw, 1000px" placeholder="blur" />
  </div>
);


const steps = [
  ["You commit", "Like always. From your terminal, or the agent commits for you."],
  ["Trail links the session", "A git hook finds the Claude Code or Codex session that edited those files."],
  ["Everything is kept", "Conversation, diff, logs and artifacts go to your store, one folder per repo."],
];

const commands = [
  ["trail init", "Writes .trail.yaml and installs two git hooks. That is the whole setup."],
  ["trail why file:line", "Blame, then the commit, then the session: the prompt, the reasoning and the edit."],
  ["trail log", "Commits in the Trail, with the sessions behind each one."],
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
        <Link href="/" className="lp-brand"><Mark size={28} /><span>Trail</span></Link>
        <nav>
          <Link href="/repos" className="lp-navlink">Demo</Link>
          <a href={GITHUB} className="lp-pill lp-dark sm" target="_blank" rel="noopener"><GithubIcon />GitHub</a>
        </nav>
      </header>

      <section className="lp-hero">
        <a className="lp-announce rise" href={GITHUB} target="_blank" rel="noopener">
          <b>Open source</b><span>Works with Claude Code and Codex</span><span className="lp-arrow">↗</span>
        </a>
        <h1 className="rise d1">Meet <Mark /> Trail</h1>
        <p className="lp-sub rise d2">
          Your agents write the code. Trail keeps the conversation that wrote it: the prompt, the reasoning,
          the logs. Linked to every commit, one command away from any line.
        </p>
        <div className="lp-ctas rise d3">
          <Link href="/repos" className="lp-pill lp-dark">See the demo</Link>
          <a href={GITHUB} className="lp-pill lp-light" target="_blank" rel="noopener"><GithubIcon />View on GitHub</a>
        </div>

        <Scene tone="sunset" className="lp-hero-art">
          <LiveDemo start={hero.commit} session={hero.link} />
        </Scene>
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
        <Scene tone="dusk" className="lp-band-art">
          <div className="lp-blame">
            <div className="lp-blame-head">git blame app/webhooks.py</div>
            <div><span>a41c9e2</span><span>maya</span><code>with db.transaction():</code></div>
            <div><span>a41c9e2</span><span>maya</span><code>if not db.processed_events…</code></div>
            <div className="hl"><span>a41c9e2</span><span>maya</span><code>return  # already handled</code></div>
            <div><span>9c03b1f</span><span>sam</span><code>capture(order.payment_intent)</code></div>
          </div>
          <div className="lp-bubble">fix webhook</div>
          <div className="lp-q">why?</div>
        </Scene>
      </section>

      <section className="lp-section">
        <p className="lp-eyebrow center">The solution</p>
        <h2 className="lp-h2">A Trail behind every commit</h2>
        <p className="lp-lead">
          Trail links each commit to the agent sessions that produced it, plus the logs and artifacts you choose,
          and stores them as one folder tree per repo.
        </p>
        <div className="lp-steps">
          {steps.map(([t, d], i) => (
            <div key={t}><span>{i + 1}</span><b>{t}</b><p>{d}</p></div>
          ))}
        </div>
        <Scene tone="sunset" className="lp-show">
          <Shot src={shotSession} alt="A session in the Trail dashboard: the prompt, tool calls and the commit it produced" url="Trail / payments-api / session" />
          <div className="lp-float lp-float-a">
            <span className="lp-float-k">Trail-Session</span>claude:{hero.sid.slice(0, 8)}…
          </div>
          <div className="lp-float lp-float-b">
            <Icon name="commit" /> Make payment webhook idempotent
          </div>
        </Scene>
      </section>

      <section className="lp-section">
        <div className="lp-grid">
          <div className="lp-card">
            <h3>Hooks, not habits</h3>
            <p>Two git hooks find the session that edited the staged files and link it when you commit.</p>
            <Scene tone="mist">
              <div className="lp-commit">
                <b>Make payment webhook idempotent</b>
                <span>Trail-Session: claude:7c1e…</span>
                <span>Trail-Link: localhost:8787/repos/payments-api/session/7c1e…</span>
              </div>
            </Scene>
          </div>
          <div className="lp-card">
            <h3>Ask any line why</h3>
            <p>Blame to commit to session to the exact prompt, reasoning and edit that wrote the line.</p>
            <Scene tone="sunset">
              <div className="lp-term">
                <div><i>$</i> trail why train.py:3</div>
                <div className="m">a91f02c Lower LR and lengthen warmup · sam · claude</div>
                <div><b>prompt</b> The 7B LoRA fine-tune keeps blowing up around step 400.</div>
                <div><b>reasoning</b> 2e-4 only delays it. Go to 1e-4 and warmup 500.</div>
                <div><b>artifacts</b> logs/run-17.log, runs/run-19/metrics.json</div>
              </div>
            </Scene>
          </div>
          <div className="lp-card">
            <h3>Logs and artifacts ride along</h3>
            <p>Training logs, metrics, CI output, reports. Whatever you list in .trail.yaml is kept with the commit.</p>
            <Scene tone="dawn">
              <div className="lp-files">
                {["logs/run-17.log", "runs/run-19/metrics.json", "logs/ci-flake-runs.txt", "reports/refund-abuse.md", "conversation.md"].map((f) => (
                  <span key={f}><Icon name="file" />{f}</span>
                ))}
              </div>
            </Scene>
          </div>
          <div className="lp-card">
            <h3>Every person, every agent</h3>
            <p>Maya on Claude Code, Leo on Codex, Sam committing by hand. One history, sessions included.</p>
            <Scene tone="dusk">
              <div className="lp-people">
                {[["M", "#4f8a6e", "maya", "claude", "Make payment webhook idempotent"],
                  ["L", "#d08a3a", "leo", "codex", "Reject duplicate refunds"],
                  ["S", "#5b6ad0", "sam", "by hand", "Bump stripe to 9.2.0"]].map(([a, c, n, h, s]) => (
                  <div key={n}>
                    <span className="lp-av sm" style={{ background: c }}>{a}</span>
                    <b>{n}</b><em>{h}</em><span className="lp-people-s">{s}</span>
                  </div>
                ))}
              </div>
            </Scene>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <h2 className="lp-h2">Browse it like GitHub</h2>
        <p className="lp-lead">Repos as folders, commits with their sessions and diffs, every conversation one click away.</p>
        <div className="lp-pair">
          <Link href="/repos" className="lp-pair-item">
            <Scene tone="mist" className="lp-pair-scene"><Shot src={shotRepos} alt="Repository list" url="Trail / repos" /></Scene>
            <b>Repositories</b><span>Every repo in the store, with commits, sessions and people.</span>
          </Link>
          <Link href="/repos/payments-api/commits" className="lp-pair-item">
            <Scene tone="dawn" className="lp-pair-scene"><Shot src={shotCommit} alt="A commit with its agent session and diff" url="Trail / payments-api / commit" /></Scene>
            <b>Commits</b><span>The diff, the artifacts, and the agent sessions behind it.</span>
          </Link>
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

      <Scene tone="sunset" className="lp-final">
        <Mark size={64} />
        <h2>See the Trail behind a commit</h2>
        <p>Three demo repos, three people, Claude Code and Codex sessions.</p>
        <div className="lp-ctas">
          <Link href="/repos" className="lp-pill lp-dark">See the demo</Link>
          <a href={GITHUB} className="lp-pill lp-light" target="_blank" rel="noopener"><GithubIcon />View on GitHub</a>
        </div>
      </Scene>

      <footer className="lp-foot">
        <span>Trail</span>
        <span>Open source. Built as a demo.</span>
        <a href={GITHUB} target="_blank" rel="noopener">GitHub</a>
      </footer>
    </div>
  );
}
