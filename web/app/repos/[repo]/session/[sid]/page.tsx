import Link from "next/link";
import { notFound } from "next/navigation";
import { RepoHeader, loadRepo } from "@/components/repo";
import { Avatar, Html, Icon, When, plural } from "@/components/ui";
import { fmtSize, handle, href, markdown, param, short } from "@/lib/format";
import { MAX_VIEW, NotFound, readText, session } from "@/lib/store";

export default async function SessionPage({ params }: { params: Promise<{ repo: string; sid: string }> }) {
  const { repo: r, sid } = await params;
  const repo = param(r);
  const s = await loadRepo(repo);
  let d: Awaited<ReturnType<typeof session>>;
  try {
    d = await session(repo, param(sid));
  } catch (e) {
    if (e instanceof NotFound) notFound();
    throw e;
  }
  const m = d.meta;
  const user = d.commits.map((c) => c.user).find(Boolean);
  const convs = await Promise.all(d.commits.map((c) => readText(repo, c.conversation_path, MAX_VIEW + 1)));
  return (
    <>
      <RepoHeader s={s} tab="sessions" />
      <main>
        <h1>{short(m.title || d.session_id, 200)} <span className="muted">{d.session_id.slice(0, 8)}</span></h1>
        <div className="muted session-by">
          <span className="label">{m.harness}</span>
          {user && <><Avatar user={user} /><b style={{ color: "var(--text)" }}>{handle(user)}</b></>}
          {" "}produced {plural(d.commits.length, "commit")}
          {m.last_seen && <> · last active <When date={m.last_seen} /></>}
          {m.branch && <> · <span className="mono">{m.branch}</span></>}
        </div>
        <div className="layout">
          <div className="timeline">
            {d.commits.map((c, i) => {
              const text = convs[i];
              const cut = text != null && text.length > MAX_VIEW;
              return (
                <div className="tl-item" key={c.sha}>
                  <details className="conv box" open={i === d.commits.length - 1}>
                    <summary className="box-head">
                      <Icon name="chev" className="chev" />
                      <Icon name="commit" />
                      <span className="grow ellip"><b>{c.subject}</b></span>
                      <span className="muted hide-sm"><When date={c.date} /></span>
                      <Link className="btn sm sha-btn" href={href.commit(repo, c.sha)}>{c.sha.slice(0, 7)}</Link>
                    </summary>
                    {text == null ? <div className="empty">Conversation not found.</div> : (
                      <>
                        {cut && (
                          <div className="note">
                            Showing the first {fmtSize(MAX_VIEW)}. <Link href={href.file(repo, c.conversation_path)}>Open the file</Link> for the rest.
                          </div>
                        )}
                        <Html html={markdown(cut ? text.slice(0, MAX_VIEW) : text)} />
                      </>
                    )}
                  </details>
                </div>
              );
            })}
          </div>
          <div className="about">
            <h2>Session</h2>
            <div className="kv" style={{ padding: 0 }}>
              <div>Harness</div><div>{m.harness}</div>
              <div>ID</div><div className="mono" style={{ wordBreak: "break-all" }}>{d.session_id}</div>
              <div>Branch</div><div className="mono">{m.branch}</div>
              <div>Stored in</div>
              <div><Link className="mono" style={{ wordBreak: "break-all" }} href={href.tree(repo, d.dir)}>{d.dir}</Link></div>
            </div>
            <hr />
            <h2>Files</h2>
            <div>
              {d.files.map((p) => (
                <Link key={p} className="chip" href={href.file(repo, p)}><Icon name="file" />{p.split("/").pop()}</Link>
              ))}
            </div>
            <hr />
            <div className="muted" style={{ fontSize: 12 }}>
              Each commit shows <span className="mono">conversation.md</span>: only the turns that led to it.{" "}
              <Link href={href.file(repo, d.dir + "/transcript.md")}>Full transcript</Link>.
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
