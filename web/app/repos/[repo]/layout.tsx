import { param } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ repo: string }> }) {
  return { title: `${param((await params).repo)} · trail` };
}

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
