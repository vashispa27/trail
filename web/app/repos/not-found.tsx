import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main>
      <div className="empty">
        Not in the trail. <Link href="/repos">Back to repositories</Link>
      </div>
    </main>
  );
}
