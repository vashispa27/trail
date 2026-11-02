import { CommitList } from "@/components/commit-list";
import { RepoHeader, loadRepo } from "@/components/repo";
import { param } from "@/lib/format";
import { commits } from "@/lib/store";

export default async function CommitsPage({ params }: { params: Promise<{ repo: string }> }) {
  const repo = param((await params).repo);
  const s = await loadRepo(repo);
  return (
    <>
      <RepoHeader s={s} tab="commits" />
      <main>
        <CommitList repo={repo} github={s.github} rows={await commits(repo)} />
      </main>
    </>
  );
}
