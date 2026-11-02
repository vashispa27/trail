import { param } from "@/lib/format";
import { NotFound, hasRepo, read } from "@/lib/store";

export async function GET(_req: Request, { params }: { params: Promise<{ repo: string; path: string[] }> }) {
  const { repo: r, path } = await params;
  const repo = param(r);
  try {
    if (!(await hasRepo(repo))) throw new NotFound(repo);
    const data = await read(repo, path.map(param).join("/"));
    return new Response(new Uint8Array(data), {
      headers: { "Content-Type": "text/plain; charset=utf-8", "X-Content-Type-Options": "nosniff" },
    });
  } catch (e) {
    if (e instanceof NotFound) return new Response("not found", { status: 404 });
    throw e;
  }
}
