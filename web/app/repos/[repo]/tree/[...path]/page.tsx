import { CodeView } from "@/components/code";
import { param } from "@/lib/format";

export default async function TreePage({ params }: { params: Promise<{ repo: string; path: string[] }> }) {
  const { repo, path } = await params;
  return <CodeView repo={repo} dir={path.map(param).join("/")} />;
}
