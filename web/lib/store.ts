/**
 * Read-only access to a trail store, for the dashboard.
 *
 * TRAIL_STORE picks the store:
 *   unset                         the demo store bundled in ./demo-store
 *   supabase://<bucket>/<prefix>  Supabase Storage (needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
 *   /some/folder                  a local store folder
 *
 * Everything is cached in memory for a few seconds.
 */
import "server-only";
import fs from "node:fs/promises";
import path from "node:path";
import { relToRepo } from "./format";

const TTL = 15_000;
export const MAX_VIEW = 512 * 1024; // bytes of a file shown in the browser; more is cut

export class NotFound extends Error {}

// --- sources -----------------------------------------------------------------

interface Source {
  label: string;
  repos(): Promise<string[]>;
  tree(repo: string): Promise<Record<string, number>>; // path relative to the repo -> size
  read(key: string): Promise<Buffer>;
}

function localSource(root: string): Source {
  async function walk(dir: string, base: string, out: Record<string, number>) {
    for (const e of await fs.readdir(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) await walk(p, base, out);
      else if (e.isFile() && e.name !== ".trail-sync.json" && !e.name.endsWith(".part"))
        out[path.relative(base, p).split(path.sep).join("/")] = (await fs.stat(p)).size;
    }
    return out;
  }
  return {
    label: root,
    async repos() {
      const entries = await fs.readdir(root, { withFileTypes: true }).catch(() => []);
      return entries.filter((e) => e.isDirectory() && !e.name.startsWith(".")).map((e) => e.name).sort();
    },
    tree: (repo) => walk(path.join(root, repo), path.join(root, repo), {}),
    read: (key) => fs.readFile(path.join(root, key)),
  };
}

function supabaseSource(url: string): Source {
  const [bucket, ...rest] = url.slice("supabase://".length).split("/");
  const prefix = rest.join("/").replace(/^\/+|\/+$/g, "");
  const base = (process.env.SUPABASE_URL || "").replace(/\/+$/, "");
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  const fullKey = (k: string) => (prefix ? `${prefix}/${k}` : k);

  async function req(method: string, p: string, body?: unknown): Promise<Response> {
    if (!base || !key) throw new Error("TRAIL_STORE is supabase:// but SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set");
    const res = await fetch(`${base}/storage/v1/${p}`, {
      method,
      headers: { Authorization: `Bearer ${key}`, apikey: key, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    if (res.status === 400 || res.status === 404) throw new NotFound(p);
    if (!res.ok) throw new Error(`supabase ${method} ${p}: ${res.status} ${(await res.text()).slice(0, 200)}`);
    return res;
  }

  type Item = { name: string; id: string | null; metadata?: { size?: number } };
  async function listDir(folder: string): Promise<Item[]> {
    const out: Item[] = [];
    for (let offset = 0; ; offset += 1000) {
      const items: Item[] = await (await req("POST", `object/list/${bucket}`, {
        prefix: folder ? folder + "/" : "", limit: 1000, offset, sortBy: { column: "name", order: "asc" },
      })).json();
      out.push(...items);
      if (items.length < 1000) return out;
    }
  }

  return {
    label: url,
    async repos() {
      return (await listDir(prefix)).filter((i) => i.id === null).map((i) => i.name).sort();
    },
    async tree(repo) {
      const root = fullKey(repo), out: Record<string, number> = {};
      const folders = [root];
      while (folders.length) {
        const batch = folders.splice(0, 8);
        const listed = await Promise.all(batch.map(async (f) => [f, await listDir(f)] as const));
        for (const [folder, items] of listed)
          for (const it of items) {
            const k = `${folder}/${it.name}`;
            if (it.id === null) folders.push(k);
            else out[k.slice(root.length + 1)] = Number(it.metadata?.size || 0);
          }
      }
      return out;
    },
    async read(k) {
      const enc = fullKey(k).split("/").map(encodeURIComponent).join("/");
      return Buffer.from(await (await req("GET", `object/authenticated/${bucket}/${enc}`)).arrayBuffer());
    },
  };
}

function source(): Source {
  const s = process.env.TRAIL_STORE;
  if (s?.startsWith("supabase://")) return supabaseSource(s);
  return localSource(path.resolve(s || path.join(process.cwd(), "demo-store")));
}

const src = source();
const cache = new Map<string, { at: number; val: Promise<unknown> }>();

function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < TTL) return hit.val as Promise<T>;
  const val = fn();
  cache.set(key, { at: Date.now(), val });
  val.catch(() => cache.delete(key));
  return val;
}

// --- types -------------------------------------------------------------------

export interface SessionRef {
  key: string;
  harness: string;
  session_id: string;
  title: string;
  dir: string;
  transcript_range: [number, number];
}

export interface CommitEntry {
  sha: string;
  subject: string;
  date: string;
  user: string;
  branch: string;
  commit_dir: string;
  sessions: SessionRef[];
}

export interface RepoSummary {
  name: string;
  github: string | null;
  remote: string | null;
  demo: boolean;
  commits: number;
  sessions: number;
  users: string[];
  updated: string | null;
  latest: CommitEntry | null;
}

export interface SessionRow extends SessionRef {
  user: string;
  updated: string;
  commits: { sha: string; subject: string; date: string }[];
}

// --- reads -------------------------------------------------------------------

export const repos = () => cached("repos", () => src.repos());

export async function hasRepo(repo: string) {
  return (await repos()).includes(repo);
}

export const tree = (repo: string) => cached(`tree:${repo}`, () => src.tree(repo));

export async function read(repo: string, rel: string): Promise<Buffer> {
  const parts = `${repo}/${rel}`.split("/").filter(Boolean);
  if (!repo || parts.includes("..") || parts.includes(".")) throw new NotFound(rel);
  try {
    return await src.read(parts.join("/"));
  } catch {
    throw new NotFound(rel);
  }
}

export async function readJson<T = any>(repo: string, rel: string): Promise<T | null> {
  try {
    return JSON.parse((await read(repo, rel)).toString("utf8"));
  } catch {
    return null;
  }
}

export async function readText(repo: string, rel: string, limit = MAX_VIEW): Promise<string | null> {
  try {
    return (await read(repo, rel)).subarray(0, limit).toString("utf8");
  } catch {
    return null;
  }
}

export function commits(repo: string): Promise<CommitEntry[]> {
  return cached(`commits:${repo}`, async () => {
    const names = Object.keys(await tree(repo)).filter((p) => p.startsWith("index/commits/") && p.endsWith(".json"));
    const rows = (await Promise.all(names.map((p) => readJson<CommitEntry>(repo, p)))).filter(Boolean) as CommitEntry[];
    return rows.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  });
}

export async function sessions(repo: string): Promise<SessionRow[]> {
  const bySid = new Map<string, SessionRow>();
  for (const c of await commits(repo)) // newest first
    for (const s of c.sessions || []) {
      if (!bySid.has(s.session_id)) bySid.set(s.session_id, { ...s, user: c.user, updated: c.date, commits: [] });
      bySid.get(s.session_id)!.commits.push({ sha: c.sha, subject: c.subject, date: c.date });
    }
  return [...bySid.values()];
}

export async function summary(repo: string): Promise<RepoSummary> {
  const [info, rows, sess] = await Promise.all([
    cached(`info:${repo}`, async () => (await readJson(repo, "repo.json")) || {}),
    commits(repo),
    sessions(repo),
  ]);
  return {
    name: repo,
    github: info.github || null,
    remote: info.remote || null,
    demo: !!info.demo,
    commits: rows.length,
    sessions: sess.length,
    users: [...new Set(rows.map((c) => c.user).filter(Boolean))].sort(),
    updated: rows[0]?.date || null,
    latest: rows[0] || null,
  };
}

export async function summaries(): Promise<RepoSummary[]> {
  const rows = await Promise.all((await repos()).map(summary));
  return rows.sort((a, b) => (b.updated || "").localeCompare(a.updated || ""));
}

export async function commit(repo: string, sha: string) {
  const hits = sha ? (await commits(repo)).filter((c) => c.sha.startsWith(sha)) : [];
  if (!hits.length) throw new NotFound(sha);
  const entry = hits[0];
  const dir = relToRepo(repo, entry.commit_dir || "");
  const info = (await readJson(repo, `${dir}/commit.json`)) || {};
  const arts: string[] = info.artifacts?.files || [];
  return {
    entry,
    commit: info as { message?: string; author?: string; files?: string[] },
    dir,
    diff: await readText(repo, `${dir}/diff.patch`, 1024 * 1024),
    artifacts: arts.map((a) => `${dir}/artifacts/${a}`),
  };
}

export async function session(repo: string, sid: string) {
  const rows = (await commits(repo)).flatMap((c) =>
    (c.sessions || []).filter((s) => s.session_id.startsWith(sid)).map((s) => [c, s] as const));
  if (!sid || !rows.length) throw new NotFound(sid);
  const sdir = relToRepo(repo, rows[0][1].dir);
  const id = rows[0][1].session_id;
  const meta = (await readJson(repo, `${sdir}/meta.json`)) || {};
  const bySha = new Map(rows.map(([c]) => [c.sha, c]));
  const list: { sha: string; subject: string; date: string; transcript_range: number[] }[] =
    meta.commits || rows.map(([c, s]) => ({ sha: c.sha, subject: c.subject, date: c.date, transcript_range: s.transcript_range }));
  const depth = sdir.split("/").length + 1;
  const files = Object.keys(await tree(repo)).filter((p) => p.startsWith(sdir + "/") && p.split("/").length === depth).sort();
  return {
    session_id: id,
    dir: sdir,
    meta: meta as { title?: string; harness?: string; branch?: string; last_seen?: string },
    files,
    commits: list.map((m) => ({
      ...m,
      user: bySha.get(m.sha)?.user || "",
      conversation_path: `${sdir}/commits/${m.sha.slice(0, 12)}/conversation.md`,
    })),
  };
}

export const storeLabel = () => src.label;
