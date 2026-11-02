"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

export function Crumbs() {
  const parts = usePathname().split("/").filter(Boolean);
  const repo = parts[0] === "repos" && parts[1] ? decodeURIComponent(parts[1]) : null;
  return (
    <div className="crumbs">
      {repo ? (
        <>
          <Link href="/repos">Trail</Link>
          <span className="sep">/</span>
          <b><Link href={`/repos/${encodeURIComponent(repo)}`}>{repo}</Link></b>
        </>
      ) : (
        <b><Link href="/repos">Trail</Link></b>
      )}
    </div>
  );
}

export function TopActions() {
  const router = useRouter();
  function toggleTheme() {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" || (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    const next = dark ? "light" : "dark";
    root.dataset.theme = next;
    try {
      localStorage.setItem("trail-theme", next);
    } catch {}
  }
  return (
    <>
      <button className="btn" title="Reload from the store" onClick={() => router.refresh()}>Refresh</button>
      <button className="btn" title="Toggle light / dark" onClick={toggleTheme}>Theme</button>
    </>
  );
}
