import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container-page py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-brand">404</p>
      <h1 className="mt-2 text-4xl font-bold tracking-tight">Seite nicht gefunden</h1>
      <p className="mt-4 text-muted">Diese Seite existiert im importierten Content-Archiv nicht.</p>
      <Link href="/" className="btn btn-primary mt-8">
        Zur Startseite
      </Link>
    </div>
  );
}
