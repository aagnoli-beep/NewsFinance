import { SystemStatus } from "@/components/system-status";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-12">
        <h1 className="text-3xl font-semibold tracking-tight">NewsFinance</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Market-impact intelligence. Evento → Sorpresa → Esposizione → Reazione → Outcome.
        </p>
      </header>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950 p-6">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          System status
        </h2>
        <SystemStatus />
      </section>

      <footer className="mt-16 text-xs text-neutral-500">
        Ricerca e analisi, non consulenza finanziaria personalizzata.
      </footer>
    </main>
  );
}
