# Generator (Teil 2)

Erzeugt aus einem Content-Archiv ([Content Schema v1.0](../docs/CONTENT-SCHEMA.md)) ein lokal lauffähiges **Next.js-Projekt** (App Router, TypeScript, Tailwind CSS). Es dient als Grundlage für ein Redesign.
Der Generator hängt nicht vom Scraper ab und lässt sich mit [`examples/sample-website-source`](../examples/sample-website-source) testen.

## Installation

Node ≥ 20.9:

```bash
cd generator && npm install
```

## Befehle

```bash
npm run generate -- --source ../outputs/example-source --output ../outputs/example-website
```

```bash
npm run sync -- --source ../outputs/example-source-neu --project ../outputs/example-website
```

```bash
npm run validate -- --source ../outputs/example-source
```

```bash
npm run check -- --project ../outputs/example-website
```

| Befehl | Was passiert |
|---|---|
| `generate` | Prüft das Archiv, kopiert die Vorlage `templates/nextjs-starter`, importiert die Inhalte und prüft das Ergebnis. Bricht ab, wenn das Ziel schon existiert. Dann `sync` verwenden oder mit `--force` alles neu erzeugen. |
| `sync` | Erneuter Import: ersetzt **nur** `content/` und `public/assets/`. Komponenten, Styles und eigene Dateien bleiben unverändert. Schreibt `content/import-report.json` mit neuen, geänderten und entfernten Seiten. Ein ungültiges Archiv lässt die bisherigen Inhalte unangetastet. |
| `validate` | Prüft ein Archiv gegen `schemas/v1` (Ajv), die Schema-Version und alle Querverweise. Fehlermeldungen nennen Datei und JSON-Pointer. |
| `check` | Prüft ein generiertes Projekt: jede Seite hat eine Route, alle Dateien sind vorhanden, interne Links zeigen auf existierende Routen, Bilder liegen in `public/`. Außerdem werden Pfadkollisionen und reservierte Pfade gemeldet und unbekannte Blocktypen gezählt. |

Danach:

```bash
cd ../outputs/example-website
```

```bash
npm install
```

```bash
npm run dev
```

Die Website läuft dann unter http://localhost:3000.

## Was im Projekt entsteht

```text
example-website/
├── app/[[...slug]]/page.tsx     # EINE Catch-all-Route für alle Seiten (generateStaticParams aus dem Manifest)
├── app/layout.tsx               # RootLayout: Header → Main → Footer
├── app/not-found.tsx            # 404 für unbekannte Pfade
├── app/globals.css              # Design-Tokens (Farben, Schrift, Radius)
├── components/layout/           # Header, Navigation (Dropdowns), MobileNavigation, Footer, Breadcrumbs
├── components/content/          # ContentRenderer + Heading, Paragraph, RichText, ImageBlock, ImageGallery,
│                                #   ListBlock, TableBlock, Button, Card/CardGrid, FAQ, CallToAction,
│                                #   EmbedBlock, CodeBlock, FormBlock, FallbackBlock
├── lib/content.ts               # Content-Loader (Manifest, Seiten, Navigation), Zod-Validierung
├── lib/schema.ts                # Zod-Modelle des Content Schema v1
├── lib/routes.ts / navigation.ts
├── content/                     # ← verwaltet vom Generator (Manifest, Navigation, Seiten-JSON)
├── public/assets/images/        # ← verwaltet vom Generator (lokale Bilder)
├── next.config.ts               # Redirects aus den Manifest-Aliases (z. B. /kontakt.html → /kontakt)
└── .redesign-tool.json          # Marker: welche Ordner der Generator verwaltet
```

- **Keine Datei pro Seite:** Die Catch-all-Route löst den Pfad über das Manifest auf, lädt `content.json` und rendert die Sections in Originalreihenfolge.
- **Nichts geht verloren:** Unbekannte Blocktypen aus neueren Schema-Versionen rendert der `FallbackBlock` als Text. `html`-Fallbacks werden ein zweites Mal mit `sanitize-html` bereinigt.
- **Formulare** werden dargestellt, aber nicht angebunden. Das gehört zum Redesign.

## Tests

```bash
npm test
```

```bash
npm run test:e2e
```

- `npm test` (vitest): Archiv-Validierung, Import/Sync (Designänderungen bleiben erhalten), Projekt-Prüfung, Content-Loader, Routing und Komponenten.
- `npm run test:e2e`: generiert → `npm install` → `next build` → `next start` → Playwright. Geprüft werden alle Routen, Bilder, Dropdown-Navigation, das Mobile-Menü, die 404-Seite und Redirects.
- Ein anderes Archiv testest du so:

```bash
npm run test:e2e -- --source <archiv>
```

Für den E2E-Test muss Playwright mit Chromium installiert sein:

```bash
npx playwright install chromium
```
