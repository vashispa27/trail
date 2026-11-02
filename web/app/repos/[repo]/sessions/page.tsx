import Link from "next/link";
import { RepoHeader, loadRepo } from "@/components/repo";
import { Avatar, Icon, When, plural } from "@/components/ui";
import { handle, href, param, short } from "@/lib/format";
import { sessions } from "@/lib/store";

export default async function SessionsPage({ params }: { params: Promise<{ repo: string }> }) {
  const repo = param((await params).repo);
  const s = await loadRepo(repo);
  const rows = await sessions(repo);
  return (
    <>
      <RepoHeader s={s} tab="sessions" />
      <main>
        <div className="box">
          <div className="box-head"><Icon name="chat" /><b className="grow">{plural(rows.length, "agent session")}</b></div>
          {rows.length ? rows.map((x) => (
            <div className="citem" key={x.session_id}>
              <Icon name="chat" className="file" />
              <div className="grow">
                <Link className="subj" href={href.session(repo, x.session_id)}>{short(x.title || x.session_id, 140)}</Link>
                <div className="by">
                  <span className="label">{x.harness}</span>
                  <Avatar user={x.user} />
                  <b>{handle(x.user)}</b> · {plural(x.commits.length, "commit")} · last <When date={x.updated} /> ·{" "}
                  <span className="mono">{x.session_id.slice(0, 8)}</span>
                </div>
              </div>
            </div>
          )) : <div className="empty">No sessions linked yet.</div>}
        </div>
      </main>
    </>
  );
}
