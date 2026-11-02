import { headers } from "next/headers";
import Link from "next/link";
import { TopActions, Crumbs } from "@/components/top";
import { GITHUB } from "@/lib/site";
import "./dashboard.css";

export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // Inside the landing page's live frame the banner is noise.
  const framed = (await headers()).get("sec-fetch-dest") === "iframe";
  const demo = !process.env.TRAIL_STORE && !framed;
  return (
    <div className="dash">
      {demo && (
        <div className="demo-banner">
          <span>Demo data: three made-up repos and three people, recorded by the real Trail hooks.</span>
          <Link href="/">About Trail</Link>
          <a href={GITHUB} target="_blank" rel="noopener">GitHub</a>
        </div>
      )}
      <div className="top">
        <Link className="logo" href="/repos"><span className="mark">T</span></Link>
        <Crumbs />
        <TopActions />
      </div>
      {children}
    </div>
  );
}
