"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./ui";

/** The real dashboard in a browser frame on the landing page: click around the demo in place. */
export function LiveDemo({ start, session }: { start: string; session: string }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [path, setPath] = useState(start);

  // The dashboard navigates with pushState, which fires no event the parent can see; poll instead.
  useEffect(() => {
    const t = setInterval(() => {
      try {
        const l = frame.current?.contentWindow?.location;
        if (l && l.pathname.startsWith("/")) setPath(l.pathname);
      } catch {}
    }, 400);
    return () => clearInterval(t);
  }, []);

  const go = (p: string) => frame.current?.contentWindow?.location.assign(p);

  return (
    <>
      <div className="lp-float lp-float-a"><code>$ trail why app/webhooks.py:9</code></div>
      <button className="lp-float lp-float-b" onClick={() => go(session)}>
        <Icon name="chat" /> Open the conversation
      </button>
      <div className="lp-browser lp-live">
        <div className="lp-browser-bar">
          <span className="lp-dots"><i /><i /><i /></span>
          <button className="lp-nav-btn" aria-label="Back" onClick={() => frame.current?.contentWindow?.history.back()}>‹</button>
          <button className="lp-nav-btn" aria-label="Forward" onClick={() => frame.current?.contentWindow?.history.forward()}>›</button>
          <button className="lp-nav-btn" aria-label="All repositories" onClick={() => go("/repos")}><Icon name="repo" /></button>
          <span className="lp-url">{decodeURIComponent(path)}</span>
          <a className="lp-open" href={path} target="_blank" rel="noopener">Open full page ↗</a>
        </div>
        <iframe ref={frame} src={start} title="Live Trail demo" />
      </div>
    </>
  );
}
