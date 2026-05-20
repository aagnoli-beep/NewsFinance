import Link from "next/link";

export function Nav() {
  return (
    <nav className="mb-12 flex items-center justify-between border-b border-neutral-900 pb-4">
      <Link href="/" className="text-sm font-semibold tracking-tight text-neutral-100">
        NewsFinance
      </Link>
      <div className="flex gap-6 text-sm">
        <Link
          href="/"
          className="text-neutral-400 hover:text-neutral-100"
        >
          Status
        </Link>
        <Link
          href="/feed"
          className="text-neutral-400 hover:text-neutral-100"
        >
          Feed
        </Link>
        <Link
          href="/clusters"
          className="text-neutral-400 hover:text-neutral-100"
        >
          Clusters
        </Link>
        <Link
          href="/coverage"
          className="text-neutral-400 hover:text-neutral-100"
        >
          Coverage
        </Link>
      </div>
    </nav>
  );
}
