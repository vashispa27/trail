/** Formatting and HTML renderers (markdown, diffs, code). Every renderer escapes its input. */

export const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export const fmtSize = (n: number) =>
  n < 1024 ? n + " Bytes" : n < 1048576 ? (n / 1024).toFixed(1) + " KB" : (n / 1048576).toFixed(1) + " MB";

export const fmtDay = (d: string) => {
  const t = new Date(d);
  return isNaN(+t) ? "" : t.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
};

export const short = (s: string | undefined | null, n: number) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");

export function ago(d: string | null | undefined) {
  const t = new Date(d || ""), s = (Date.now() - +t) / 1000;
  if (isNaN(+t)) return "";
  if (s < 60) return "just now";
  for (const [n, u] of [[31536000, "year"], [2592000, "month"], [86400, "day"], [3600, "hour"], [60, "minute"]] as const)
    if (s >= n) {
      const v = Math.floor(s / n);
      return `${v} ${u}${v > 1 ? "s" : ""} ago`;
    }
  return "";
}

export function hue(s: string) {
  let h = 0;
  for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 360;
}

export const handle = (u: string | null | undefined) => String(u || "?").split("@")[0];

export const ghOwner = (gh: string | null) => (gh ? gh.replace(/^https:\/\/github\.com\//, "").split("/")[0] : null);

/** "git@github.com:acme/web-app.git" -> "acme/web-app" (for repos with no linkable GitHub URL). */
export const remoteName = (remote: string | null) =>
  remote ? remote.replace(/^(?:\w+:\/\/)?(?:[^@/]+@)?[^:/]+[:/]/, "").replace(/\.git$/, "") : null;

/** Index paths start with the repo folder; pages use paths relative to it. */
export const relToRepo = (repo: string, p: string) => (p.startsWith(repo + "/") ? p.slice(repo.length + 1) : p);

export const enc = (p: string) => p.split("/").map(encodeURIComponent).join("/");

export const href = {
  repo: (r: string) => "/repos/" + encodeURIComponent(r),
  tree: (r: string, p?: string) => (p ? href.repo(r) + "/tree/" + enc(p) : href.repo(r)),
  file: (r: string, p: string) => href.repo(r) + "/blob/" + enc(p),
  raw: (r: string, p: string) => href.repo(r) + "/raw/" + enc(p),
  commits: (r: string) => href.repo(r) + "/commits",
  commit: (r: string, s: string) => href.repo(r) + "/commit/" + encodeURIComponent(s),
  sessions: (r: string) => href.repo(r) + "/sessions",
  session: (r: string, s: string) => href.repo(r) + "/session/" + encodeURIComponent(s),
};

/** Route params arrive percent-encoded in some cases; decode once, leniently. */
export const param = (s: string) => {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
};

// --- markdown ----------------------------------------------------------------

function inline(s: string) {
  const codes: string[] = [];
  s = esc(s).replace(/`([^`]+)`/g, (_, c) => {
    codes.push(c);
    return "\u0000" + (codes.length - 1) + "\u0000";
  });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => (/^(https?:\/\/|#|\/)/.test(u) ? `<a href="${u}">${t}</a>` : m));
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*\w])\*([^*\s][^*]*)\*(?!\w)/g, "$1<em>$2</em>");
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => "<code>" + codes[+i] + "</code>");
}

export function markdown(src: string) {
  const out: string[] = [], lines = src.replace(/\r/g, "").split("\n");
  let para: string[] = [], list: string | null = null;
  const flush = () => {
    if (para.length) out.push("<p>" + inline(para.join(" ")) + "</p>");
    para = [];
  };
  const endList = () => {
    if (list) out.push("</" + list + ">");
    list = null;
  };
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    let m: RegExpMatchArray | null;
    if ((m = ln.match(/^\s*(```+|~~~+)/))) {
      flush(); endList();
      const body: string[] = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(m[1]); i++) body.push(lines[i]);
      out.push("<pre><code>" + esc(body.join("\n")) + "</code></pre>");
    } else if ((m = ln.match(/^(#{1,6})\s+(.*)$/))) {
      flush(); endList();
      out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`);
    } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(ln)) {
      flush(); endList();
      out.push("<hr>");
    } else if ((m = ln.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/))) {
      flush();
      const kind = /\d/.test(m[1]) ? "ol" : "ul";
      if (list !== kind) {
        endList();
        out.push("<" + kind + ">");
        list = kind;
      }
      out.push("<li>" + inline(m[2]) + "</li>");
    } else if ((m = ln.match(/^>\s?(.*)$/))) {
      flush(); endList();
      out.push("<blockquote>" + inline(m[1]) + "</blockquote>");
    } else if (!ln.trim()) {
      flush(); endList();
    } else {
      endList();
      para.push(ln.trim());
    }
  }
  flush(); endList();
  return '<div class="md">' + out.join("\n") + "</div>";
}

// --- code and diffs ----------------------------------------------------------

export const diffLine = (l: string) => {
  const c = l[0] === "+" ? "a" : l[0] === "-" ? "d" : l.startsWith("@@") ? "h" : "";
  return `<div class="${c}">${esc(l) || "&nbsp;"}</div>`;
};

export const diffHtml = (src: string) => '<div class="diff">' + src.replace(/\r/g, "").split("\n").map(diffLine).join("") + "</div>";

export function codeHtml(text: string) {
  const lines = text.replace(/\r/g, "").replace(/\n$/, "").split("\n");
  return '<div class="code-wrap"><table class="code"><tbody>' +
    lines.map((l, i) => `<tr><td class="n">${i + 1}</td><td class="l">${esc(l) || " "}</td></tr>`).join("") +
    "</tbody></table></div>";
}

export function renderContent(path: string, text: string, cut: boolean) {
  const name = path.split("/").pop()!.toLowerCase();
  if (cut) text = text.slice(0, text.lastIndexOf("\n") + 1 || undefined);
  if (name.endsWith(".md")) return markdown(text);
  if (name.endsWith(".json") && !cut) {
    try {
      return codeHtml(JSON.stringify(JSON.parse(text), null, 2));
    } catch {}
  }
  if (name.endsWith(".patch") || name.endsWith(".diff")) return diffHtml(text);
  return codeHtml(text);
}

/** "diff --git a/x b/x" blocks -> [{file, adds, dels, lines}]; the --stat preamble is dropped. */
export function splitDiff(src: string) {
  const files: { file: string; adds: number; dels: number; lines: string[] }[] = [];
  let cur: (typeof files)[number] | null = null;
  for (const l of src.replace(/\r/g, "").split("\n")) {
    const m = l.match(/^diff --git a\/(.*) b\/(.*)$/);
    if (m) {
      cur = { file: m[2], adds: 0, dels: 0, lines: [] };
      files.push(cur);
      continue;
    }
    if (!cur || /^(index |--- |\+\+\+ |new file mode|deleted file mode|similarity |rename )/.test(l)) continue;
    if (l[0] === "+") cur.adds++;
    else if (l[0] === "-") cur.dels++;
    cur.lines.push(l);
  }
  return files;
}

/** Commit message body with links; Trail-Link URLs point back into this dashboard. */
export function linkBody(body: string) {
  return esc(body).replace(/https?:\/\/[^\s<]+/g, (u) => {
    const m = u.match(/(?:\/repos\/|#\/)([^/\s]+)\/session\/([^/\s]+)$/);
    return m ? `<a href="/repos/${m[1]}/session/${m[2]}">${u}</a>` : `<a href="${u}" target="_blank" rel="noopener">${u}</a>`;
  });
}
