import Link from "next/link";
import { GithubLine } from "@/components/repo";
import { GhAvatar, Icon, When, plural } from "@/components/ui";
import { href } from "@/lib/format";
import { summaries } from "@/lib/store";

export const metadata = { title: "Repositories · Trail" };

export default async function Home() {
  const repos = await summaries();
  return (
    <main>
      <h2>Repositories <span className="counter">{repos.length}</span></h2>
      <div className="repo-list">
        {repos.length ? repos.map((r) => (
          <div className="item" key={r.name}>
            <div className="grow">
              <h3>
                <Icon name="repo" className="muted" />
                <Link href={href.repo(r.name)}>{r.name}</Link>
                <span className="label">{r.demo ? "Demo" : "Trail"}</span>
              </h3>
              <GithubLine s={r} />
              {r.latest && (
                <div className="muted ellip" style={{ marginBottom: 8 }}>
                  Latest: <Link className="muted" href={href.commit(r.name, r.latest.sha)}>{r.latest.subject}</Link>
                </div>
              )}
              <div className="meta">
                <span><Icon name="commit" />{plural(r.commits, "commit")}</span>
                <span><Icon name="chat" />{plural(r.sessions, "session")}</span>
                <span><Icon name="people" />{plural(r.users.length, "person", "people")}</span>
                {r.updated && <span>Updated <When date={r.updated} /></span>}
              </div>
            </div>
            {r.github && (
              <a className="hide-sm" href={r.github} target="_blank" rel="noopener" title="Open on GitHub">
                <GhAvatar github={r.github} />
              </a>
            )}
          </div>
        )) : (
          <div className="empty">The store has no repos yet. Run <span className="mono">trail init</span> in a repo and commit.</div>
        )}
      </div>
    </main>
  );
}
