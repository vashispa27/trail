import { CodeView } from "@/components/code";

export default async function RepoPage({ params }: { params: Promise<{ repo: string }> }) {
  const { repo } = await params;
  return <CodeView repo={repo} dir="" />;
}
