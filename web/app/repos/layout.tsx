import Link from "next/link";
import { TopActions, Crumbs } from "@/components/top";
import { GITHUB } from "@/lib/site";
import "./dashboard.css";

export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const demo = !process.env.TRAIL_STORE;
  return (
    <div className="dash">
      {demo && (
        <div className="demo-banner">
          <span>Demo data: three made-up repos and three people, recorded by the real trail hooks.</span>
          <Link href="/">About trail</Link>
          <a href={GITHUB} target="_blank" rel="noopener">GitHub</a>
        </div>
      )}
      <div className="top">
        <Link className="logo" href="/repos"><span className="mark">t</span></Link>
        <Crumbs />
        <TopActions />
      </div>
      {children}
    </div>
  );
}
