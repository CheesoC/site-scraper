# Generierte Website (Redesign-Grundgerüst)

Erzeugt vom Website-Generator aus einem Content-Archiv (Content Schema v1.0).

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # Produktions-Build
```

## Aufbau

| Ordner | Inhalt | Wer ändert ihn? |
|---|---|---|
| `content/` | Manifest, Navigation, Seiteninhalte (JSON) | **nur der Generator** (`npm run sync` im Generator) |
| `public/assets/` | importierte Bilder | **nur der Generator** |
| `app/`, `components/`, `lib/`, `app/globals.css` | Routing, Layout, Komponenten, Design | **du** – hier findet das Redesign statt |

- `app/[[...slug]]/page.tsx` – eine Catch-all-Route für alle Seiten (keine Datei pro Seite).
- `lib/content.ts` – lädt und validiert die Inhalte (Zod-Modelle in `lib/schema.ts`).
- `components/content/ContentRenderer.tsx` – setzt Sections und Blöcke in Originalreihenfolge in Komponenten um.
- `components/content/ContentSection.tsx` – Layout pro Section-Typ (Hero, Cards, FAQ, …).
- `app/globals.css` – Design-Tokens (Farben, Schrift, Radius) für das Redesign.

## Inhalte aktualisieren

Im Generator-Verzeichnis:

```bash
npm run sync -- --source <neues-archiv> --project <dieses-projekt>
```

Ersetzt nur `content/` und `public/assets/` (siehe `.redesign-tool.json`). Deine Komponenten und Styles bleiben unverändert.
