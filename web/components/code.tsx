import Link from "next/link";
import { fmtSize, href, param } from "@/lib/format";
import { sessions, tree } from "@/lib/store";
import { About, LatestBar, PathCrumbs, RepoHeader, loadRepo } from "./repo";
import { Icon, When } from "./ui";

function listing(files: Record<string, number>, dir: string) {
  const pre = dir ? dir + "/" : "", dirs: Record<string, number> = {}, here: { path: string; size: number }[] = [];
  for (const [p, size] of Object.entries(files)) {
    if (!p.startsWith(pre)) continue;
    const rest = p.slice(pre.length), i = rest.indexOf("/");
    if (i < 0) here.push({ path: p, size });
    else dirs[rest.slice(0, i)] = (dirs[rest.slice(0, i)] || 0) + 1;
  }
  return {
    dirs: Object.keys(dirs).sort().map((d) => ({ name: d, count: dirs[d] })),
    files: here.sort((a, b) => a.path.localeCompare(b.path)),
  };
}

/** The Code tab: a folder listing, plus recent sessions and the About sidebar at the root. */
export async function CodeView({ repo: rawRepo, dir }: { repo: string; dir: string }) {
  const repo = param(rawRepo);
  const s = await loadRepo(repo);
  const [files, sess] = await Promise.all([tree(repo), sessions(repo)]);
  const { dirs, files: here } = listing(files, dir);
  const recent = sess.slice(0, 5);
  return (
    <>
      <RepoHeader s={s} tab="code" />
      <main>
        <div className="layout">
          <div>
            {dir && <PathCrumbs repo={repo} path={dir} />}
            <div className="box">
              <LatestBar s={s} />
              {dir && (
                <div className="row">
                  <Link className="name grow" href={href.tree(repo, dir.split("/").slice(0, -1).join("/"))}>. .</Link>
                </div>
              )}
              {dirs.map((d) => (
                <div className="row" key={d.name}>
                  <Icon name="dir" className="dir" />
                  <Link className="name grow" href={href.tree(repo, (dir ? dir + "/" : "") + d.name)}>{d.name}</Link>
                  <span className="muted">{d.count} file{d.count > 1 ? "s" : ""}</span>
                </div>
              ))}
              {here.map((f) => (
                <div className="row" key={f.path}>
                  <Icon name="file" className="file" />
                  <Link className="name grow" href={href.file(repo, f.path)}>{f.path.split("/").pop()}</Link>
                  <span className="muted">{fmtSize(f.size)}</span>
                </div>
              ))}
              {!dirs.length && !here.length && <div className="empty">Empty folder.</div>}
            </div>
            {!dir && recent.length > 0 && (
              <div className="box" style={{ marginTop: 24 }}>
                <div className="box-head"><b>Recent agent sessions</b></div>
                {recent.map((x) => (
                  <div className="row" key={x.session_id}>
                    <Icon name="chat" className="file" />
                    <Link className="name grow" href={href.session(repo, x.session_id)}>{x.title || x.session_id}</Link>
                    <span className="label">{x.harness}</span>
                    <span className="muted hide-sm"><When date={x.updated} /></span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <About s={s} files={files} />
        </div>
      </main>
    </>
  );
}
