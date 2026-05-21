import { Nav } from "@/components/nav";
import { SystemStatus } from "@/components/system-status";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Nav />

      <header className="mb-12">
        <h1 className="text-3xl font-semibold tracking-tight">NewsFinance</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Sistema di market-impact intelligence. Trasforma news, earnings e dati
          macro in eventi classificati con sorpresa, esposizione e reazione
          di mercato.
        </p>
      </header>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950 p-6">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Stato del sistema
        </h2>
        <SystemStatus />
      </section>

      <section className="mt-6 rounded-lg border border-neutral-900 bg-neutral-950/50 p-6 text-sm text-neutral-400">
        <p className="font-medium text-neutral-300">Come usare le sezioni</p>
        <ul className="mt-3 space-y-2 text-xs leading-relaxed">
          <li>
            <strong className="text-neutral-200">News</strong> — flusso grezzo di
            tutto ciò che arriva dalle fonti, prima di essere interpretato.
          </li>
          <li>
            <strong className="text-neutral-200">Eventi</strong> — news raggruppate
            per evento unico, classificate dall'AI (tipo evento, entità coinvolte,
            sorpresa rispetto alle attese).
          </li>
          <li>
            <strong className="text-neutral-200">Avvisi</strong> — solo gli eventi
            importanti, con impatto stimato, aziende coinvolte e reazione del
            mercato. La pagina da consultare ogni giorno.
          </li>
          <li>
            <strong className="text-neutral-200">Copertura</strong> — quali ticker
            sono monitorati e con quanto storico di prezzi.
          </li>
        </ul>
      </section>

      <footer className="mt-16 text-xs text-neutral-500">
        Ricerca e analisi, non consulenza finanziaria personalizzata.
      </footer>
    </main>
  );
}
