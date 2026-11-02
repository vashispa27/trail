import Link from "next/link";
import { notFound } from "next/navigation";
import { fmtSize, ghOwner, handle, href, remoteName } from "@/lib/format";
import { hasRepo, summary, type RepoSummary } from "@/lib/store";
import { Avatar, Icon, When } from "./ui";

type Tab = "code" | "commits" | "sessions";

/** Loads the repo summary (404 for unknown repos) and draws the GitHub-style header. */
export async function loadRepo(repo: string) {
  if (!(await hasRepo(repo))) notFound();
  return summary(repo);
}

export function RepoHeader({ s, tab }: { s: RepoSummary; tab: Tab }) {
  const owner = ghOwner(s.github);
  const t = (id: Tab, icon: "code" | "commit" | "chat", label: string, to: string, n?: number) => (
    <Link className={tab === id ? "on" : ""} href={to}>
      <Icon name={icon} />
      {label}
      {n != null && <span className="counter">{n}</span>}
    </Link>
  );
  return (
    <div className="rhead">
      <div className="rtitle">
        <Icon name="repo" />
        {owner && (
          <>
            <a href={s.github!.replace(/\/[^/]+$/, "")} target="_blank" rel="noopener">{owner}</a>
            <span className="muted">/</span>
          </>
        )}
        <b><Link href={href.repo(s.name)}>{s.name}</Link></b>
        <span className="label">{s.demo ? "Demo" : "Trail"}</span>
        <span className="grow" />
        {s.github && (
          <a className="btn" href={s.github} target="_blank" rel="noopener">
            <Icon name="github" />View on GitHub
          </a>
        )}
      </div>
      <nav className="tabs">
        {t("code", "code", "Code", href.repo(s.name))}
        {t("commits", "commit", "Commits", href.commits(s.name), s.commits)}
        {t("sessions", "chat", "Sessions", href.sessions(s.name), s.sessions)}
      </nav>
    </div>
  );
}

export function GithubLine({ s, className = "gh" }: { s: RepoSummary; className?: string }) {
  if (s.github)
    return (
      <a className={className} href={s.github} target="_blank" rel="noopener">
        <Icon name="github" />{s.github.replace("https://", "")}
      </a>
    );
  const name = remoteName(s.remote);
  return (
    <div className={`${className} plain`}>
      <Icon name="github" />
      <span>{name ? `${name}${s.demo ? " (demo, not on GitHub)" : ""}` : "No GitHub remote"}</span>
    </div>
  );
}

export function PathCrumbs({ repo, path }: { repo: string; path: string }) {
  const parts = path.split("/").filter(Boolean);
  return (
    <div className="path">
      <Link href={href.repo(repo)}>{repo}</Link>
      {parts.map((p, i) => (
        <span key={i}>
          <span className="sep">/</span>
          {i === parts.length - 1 ? <b>{p}</b> : <Link href={href.tree(repo, parts.slice(0, i + 1).join("/"))}>{p}</Link>}
        </span>
      ))}
    </div>
  );
}

export function LatestBar({ s }: { s: RepoSummary }) {
  const c = s.latest;
  if (!c) return <div className="box-head"><span className="muted">No commits recorded yet.</span></div>;
  return (
    <div className="box-head">
      <Avatar user={c.user} />
      <b>{handle(c.user)}</b>
      <Link className="grow ellip muted" href={href.commit(s.name, c.sha)}>{c.subject}</Link>
      <Link className="muted mono hide-sm" href={href.commit(s.name, c.sha)}>{c.sha.slice(0, 7)}</Link>
      <span className="muted hide-sm">· <When date={c.date} /></span>
      <Link className="muted" href={href.commits(s.name)}>
        <Icon name="history" /> <b>{s.commits}</b> Commits
      </Link>
    </div>
  );
}

export function About({ s, files }: { s: RepoSummary; files: Record<string, number> }) {
  const paths = Object.keys(files);
  const total = Object.values(files).reduce((n, x) => n + x, 0);
  const arts = paths.filter((p) => p.includes("/artifacts/")).length;
  return (
    <div className="about">
      <h2>About</h2>
      <p>Agent sessions, logs and artifacts linked to every commit of <b>{s.name}</b>.</p>
      <GithubLine s={s} className="gh-link" />
      <div className="line"><Icon name="commit" /><Link href={href.commits(s.name)}>{s.commits}</Link> commits</div>
      <div className="line"><Icon name="chat" /><Link href={href.sessions(s.name)}>{s.sessions}</Link> agent sessions</div>
      <div className="line"><Icon name="file" /><b>{arts}</b>&nbsp;artifacts · {fmtSize(total)}</div>
      {s.updated && <div className="line"><Icon name="history" />Updated <When date={s.updated} /></div>}
      <hr />
      <h2>Contributors <span className="counter">{s.users.length}</span></h2>
      <div className="people">{s.users.map((u) => <Avatar key={u} user={u} lg />)}</div>
      <div style={{ marginTop: 8 }}>
        {s.users.map((u) => <div key={u} className="muted" style={{ fontSize: 12 }}>{u}</div>)}
      </div>
    </div>
  );
}
