"use client";

import Link from "next/link";
import { useState } from "react";
import { fmtDay, handle, href } from "@/lib/format";
import type { CommitEntry } from "@/lib/store";
import { Avatar, Icon, SessionChips, When } from "./ui";

/** Commits grouped by day, with a filter box. */
export function CommitList({ repo, github, rows }: { repo: string; github: string | null; rows: CommitEntry[] }) {
  const [q, setQ] = useState("");
  const needle = q.toLowerCase();
  const list = rows.filter((c) =>
    (c.sha + c.subject + c.user + c.branch + (c.sessions || []).map((x) => x.title + x.session_id + x.harness).join(" "))
      .toLowerCase().includes(needle));
  const days: { d: string; items: CommitEntry[] }[] = [];
  for (const c of list) {
    const d = fmtDay(c.date);
    if (!days.length || days[days.length - 1].d !== d) days.push({ d, items: [] });
    days[days.length - 1].items.push(c);
  }
  return (
    <>
      <input className="filter" type="search" placeholder="Filter by message, sha, person or session"
             value={q} onChange={(e) => setQ(e.target.value)} />
      {days.length ? days.map((g) => (
        <div className="day-group" key={g.d}>
          <div className="day"><Icon name="commit" />Commits on {g.d}</div>
          <div className="box">
            {g.items.map((c) => (
              <div className="citem" key={c.sha}>
                <div className="grow">
                  <Link className="subj" href={href.commit(repo, c.sha)}>{c.subject}</Link>
                  <div><SessionChips repo={repo} sessions={c.sessions} /></div>
                  <div className="by">
                    <Avatar user={c.user} />
                    <b>{handle(c.user)}</b> committed <When date={c.date} />
                    {c.branch && <> · <span className="mono">{c.branch}</span></>}
                  </div>
                </div>
                <div className="acts">
                  {github && (
                    <a className="btn sm" href={`${github}/commit/${c.sha}`} target="_blank" rel="noopener" title="View on GitHub">
                      <Icon name="github" />
                    </a>
                  )}
                  <Link className="btn sm sha-btn" href={href.commit(repo, c.sha)}>{c.sha.slice(0, 7)}</Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )) : <div className="empty">No matching commits.</div>}
    </>
  );
}
