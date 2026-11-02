import { notFound } from "next/navigation";
import { PathCrumbs, RepoHeader, loadRepo } from "@/components/repo";
import { Html } from "@/components/ui";
import { fmtSize, href, param, renderContent } from "@/lib/format";
import { MAX_VIEW, NotFound, read } from "@/lib/store";

export default async function FilePage({ params }: { params: Promise<{ repo: string; path: string[] }> }) {
  const { repo: r, path: p } = await params;
  const repo = param(r), path = p.map(param).join("/");
  const s = await loadRepo(repo);
  let data: Buffer;
  try {
    data = await read(repo, path);
  } catch (e) {
    if (e instanceof NotFound) notFound();
    throw e;
  }
  const cut = data.length > MAX_VIEW;
  const text = data.subarray(0, MAX_VIEW).toString("utf8");
  const raw = href.raw(repo, path);
  return (
    <>
      <RepoHeader s={s} tab="code" />
      <main>
        <PathCrumbs repo={repo} path={path} />
        <div className="box">
          <div className="box-head">
            <span className="grow muted">{cut ? "" : `${text ? text.split("\n").length : 0} lines · `}{fmtSize(data.length)}</span>
            <a className="btn sm" href={raw} target="_blank">Raw</a>
          </div>
          {cut && (
            <div className="note">
              Showing the first {fmtSize(MAX_VIEW)} of {fmtSize(data.length)}. <a href={raw} target="_blank">View raw</a> for the whole file.
            </div>
          )}
          <Html html={renderContent(path, text, cut)} />
        </div>
      </main>
    </>
  );
}
