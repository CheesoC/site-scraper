# {{SITE_NAME}} – Redesign

Dieses Projekt ist die Grundlage für ein komplettes Redesign der Website {{SOURCE_URL}}.
Es wurde automatisch aus einem Scrape erzeugt (Stand: {{CRAWLED_AT}}, {{PAGE_COUNT}} Seiten): Inhalte, Bilder und Navigation der Originalseite sind übernommen, soweit der Scrape sie erfasst hat; das Design ist ein neutrales Grundgerüst. Vor größeren Annahmen kurz in `content/` prüfen, was tatsächlich vorhanden ist.

**Ziel:** neues Design, gleiche Inhalte. Struktur, Komponenten und Seitenaufbau dürfen frei geändert werden.

## Regeln

- Vorhandene Texte nie umformulieren, kürzen oder inhaltlich verändern – der Wortlaut der Originalseite bleibt erhalten. Wo und wie ein Text im neuen Design eingesetzt wird (Reihenfolge, Aufteilung, Platzierung), ist dagegen frei.
- Neue, ergänzende Texte sind erlaubt, wo das Design sie braucht (z. B. Überschriften, Teaser, Button-Beschriftungen). Sie dürfen den Originalinhalten aber nicht widersprechen und keine neuen Fakten (Termine, Angebote, Zahlen) behaupten.
- Keine Seite und kein Bild stillschweigend weglassen. Was bewusst entfällt (z. B. technische Links der alten Website wie Login oder Druckansicht), kurz nennen.
- Vor „fertig“: `npm run typecheck` und `npm run build` müssen fehlerfrei laufen.

## Aufbau

Next.js (App Router), React, Tailwind CSS 4, TypeScript. Start: `npm install`, dann `npm run dev` (http://localhost:3000).

| Pfad | Inhalt |
|---|---|
| `content/manifest.json` | alle Seiten: `path`, Titel, Original-URL, `aliases` (alte Pfade, werden in `next.config.ts` zu Redirects) |
| `content/navigation.json` | Hauptmenü (`main`, verschachtelt über `children`), Footer, Logo, CTA |
| `content/pages/<seite>/content.json` | Inhalt einer Seite: `sections` (Typ `hero`, `content`, `cards`, `faq`, `gallery`, …) mit `blocks` (Überschrift, Absatz, Bild, Liste, Tabelle, …) in Originalreihenfolge |
| `public/assets/` | alle Bilder der Originalseite |
| `lib/content.ts` | lädt die Inhalte: `getPage(path)`, `getAllPaths()`, `getManifest()`, `getNavigation()` |
| `lib/schema.ts` | Zod-Modelle aller Inhaltstypen – Referenz für die Datenstruktur |
| `app/[[...slug]]/page.tsx` | eine Route für alle Seiten |
| `components/content/` | eine Komponente pro Block- und Section-Typ, `ContentRenderer.tsx` setzt sie zusammen |
| `components/layout/` | Header, Navigation, Mobile-Navigation, Footer, Breadcrumbs |
| `app/globals.css` | Design-Tokens (Farben, Schrift, Radius) |

## Hinweise

- Die Inhalte sind Daten aus dem Scrape und dürfen direkt bearbeitet werden. Ein späterer Content-Import (`npm run sync` im Generator) würde `content/` und `public/assets/` allerdings komplett ersetzen.
- Eine eigene Gestaltung für einzelne Seiten (z. B. eine neue Startseite) am besten in `app/[[...slug]]/page.tsx` nach `path` verzweigen. Eine zusätzliche `app/page.tsx` kollidiert mit der optionalen Catch-all-Route.
- Die Section-Typen wurden aus dem Original-HTML abgeleitet. Ist eine Seite überwiegend als `content` typisiert, lohnt es sich, Inhalte gezielt in eigene Komponenten zu überführen.
