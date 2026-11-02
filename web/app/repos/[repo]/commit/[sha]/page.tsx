import Link from "next/link";
import { notFound } from "next/navigation";
import { RepoHeader, loadRepo } from "@/components/repo";
import { Avatar, Html, Icon, When } from "@/components/ui";
import { diffLine, enc, handle, href, linkBody, param, relToRepo, splitDiff } from "@/lib/format";
import { NotFound, commit } from "@/lib/store";

export default async function CommitPage({ params }: { params: Promise<{ repo: string; sha: string }> }) {
  const { repo: r, sha } = await params;
  const repo = param(r);
  const s = await loadRepo(repo);
  let d: Awaited<ReturnType<typeof commit>>;
  try {
    d = await commit(repo, param(sha));
  } catch (e) {
    if (e instanceof NotFound) notFound();
    throw e;
  }
  const e = d.entry, c = d.commit;
  const body = (c.message || "").split("\n").slice(1).join("\n").trim();
  const files = d.diff ? splitDiff(d.diff) : [];
  const adds = files.reduce((n, f) => n + f.adds, 0), dels = files.reduce((n, f) => n + f.dels, 0);
  return (
    <>
      <RepoHeader s={s} tab="commits" />
      <main>
        <div className="box">
          <div style={{ padding: 16 }}>
            <h1 className="ctitle">{e.subject}</h1>
            {body && <Html className="cbody" html={linkBody(body)} />}
          </div>
          <div className="cfoot">
            <Avatar user={e.user} />
            <b style={{ color: "var(--text)" }}>{handle(e.user)}</b> committed <When date={e.date} />
            {e.branch && <> · <span className="mono">{e.branch}</span></>}
            <span className="grow" />
            {s.github && (
              <a className="btn sm" href={`${s.github}/commit/${e.sha}`} target="_blank" rel="noopener">
                <Icon name="github" />View on GitHub
              </a>
            )}
            <span>commit <span className="mono" style={{ color: "var(--text)" }}>{e.sha}</span></span>
          </div>
        </div>

        <div className="box">
          <div className="box-head">
            <Icon name="chat" />
            <b className="grow">Agent sessions behind this commit</b>
            <span className="counter">{(e.sessions || []).length}</span>
          </div>
          {(e.sessions || []).length ? e.sessions.map((x) => (
            <div className="row" key={x.session_id}>
              <Icon name="chat" className="file" />
              <div className="grow">
                <Link className="name" href={href.session(repo, x.session_id)}><b>{x.title || x.session_id}</b></Link>
                <div className="muted mono" style={{ fontSize: 12 }}>
                  {x.harness}:{x.session_id} · transcript lines {(x.transcript_range || []).join("–")}
                </div>
              </div>
              <Link className="btn sm" href={href.file(repo, `${relToRepo(repo, x.dir)}/commits/${e.sha.slice(0, 12)}/conversation.md`)}>
                Conversation
              </Link>
            </div>
          )) : <div className="empty">No agent session linked. A person made this commit by hand.</div>}
        </div>

        {d.artifacts.length > 0 && (
          <div className="box">
            <div className="box-head">
              <Icon name="file" /><b className="grow">Artifacts</b><span className="counter">{d.artifacts.length}</span>
            </div>
            {d.artifacts.map((p) => (
              <div className="row" key={p}>
                <Icon name="file" className="file" />
                <Link className="name grow" href={href.file(repo, p)}>{p.slice(d.dir.length + "/artifacts/".length)}</Link>
              </div>
            ))}
          </div>
        )}

        <div style={{ margin: "24px 0 8px" }} className="muted">
          Showing <b style={{ color: "var(--text)" }}>{files.length} changed file{files.length === 1 ? "" : "s"}</b> with{" "}
          <span className="stat"><b className="p">{adds} additions</b> and <b className="m">{dels} deletions</b></span>.
        </div>
        {files.map((f) => (
          <div className="box" key={f.file}>
            <div className="fhead">
              <span className="grow">{f.file}</span>
              <span className="stat"><span className="p">+{f.adds}</span> <span className="m">−{f.dels}</span></span>
              {s.github && (
                <a className="btn sm" href={`${s.github}/blob/${e.sha}/${enc(f.file)}`} target="_blank" rel="noopener" title="View file on GitHub">
                  <Icon name="github" />
                </a>
              )}
            </div>
            <Html className="diff" html={f.lines.map(diffLine).join("")} />
          </div>
        ))}
        {!files.length && d.diff == null && <div className="box"><div className="empty">No diff stored.</div></div>}
      </main>
    </>
  );
}
