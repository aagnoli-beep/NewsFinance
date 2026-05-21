import Link from "next/link";

export function Nav() {
  return (
    <nav className="mb-10 border-b border-neutral-900 pb-4">
      <Link
        href="/"
        className="text-sm font-semibold tracking-tight text-neutral-100 hover:text-emerald-400"
      >
        NewsFinance
      </Link>
    </nav>
  );
}
