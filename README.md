# site-scraper – Website Scraper & Redesign Starter

Zwei unabhängige Module mit gemeinsamer, versionierter Datenschnittstelle:

1. **`scraper/`** (Python, Crawl4AI): erfasst eine Website (Unterseiten, Navigation, Inhalte, Bilder, Metadaten) als standardisiertes Content-Archiv.
2. **`generator/`** (Node/TypeScript): erzeugt aus dem Archiv ein lokal lauffähiges Next.js-Projekt als Grundlage für ein Redesign.

Die Schnittstelle ist in [`schemas/v1`](schemas/v1) definiert und in [`docs/CONTENT-SCHEMA.md`](docs/CONTENT-SCHEMA.md) beschrieben.

> Work in progress – siehe [`docs/00-GESAMTPLAN.md`](docs/00-GESAMTPLAN.md).
