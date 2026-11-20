# Teil 2 – Website Grundgerüst Generator

## 13. Ziel

Der Generator liest ein Content-Archiv (Schema v1.0) und erstellt daraus eine funktionierende Next.js-Website mit allen Unterseiten, Texten, Bildern und Navigationsstrukturen in einem neutralen, responsiven Layout. Kein visueller Klon, sondern Ausgangspunkt für ein Redesign.

**Ausgabe:** lokal ausführbares Next.js-Projekt mit dynamischen Routen, funktionierender Navigation, Darstellung aller unterstützten Blöcke, lokalen Bildern, wiederverwendbaren Komponenten und responsivem Standardlayout.

## 14. Stack

Next.js (App Router) · React · TypeScript · Tailwind CSS · JSON als Content-Quelle · JSON Schema / Zod · Node.js.

## 15. Projektgenerierung

Das Frontend entsteht aus einer **festen, wiederverwendbaren Vorlage** (`generator/templates/nextjs-starter`) mit Konfiguration, dynamischem Routing, Content-Loader, Navigation, Standardkomponenten, Tailwind, Layout und Fehlerbehandlung. Beim Generieren werden nur Archiv und Assets importiert.

## 16. Dynamisches Routing

**Keine separaten Seitendateien pro Unterseite**, sondern eine Catch-all-Route `app/[[...slug]]/page.tsx`:

1. Next.js empfängt den Pfad → 2. Loader normalisiert ihn → 3. Lookup im Manifest → 4. `content.json` laden → 5. ContentRenderer → 6. gemeinsames Layout.

Nicht existierende Seiten → 404. Ursprüngliche URL-Varianten optional über Redirects.

## 17. Content-Loader

Manifest laden, Pfade auflösen, Content laden und validieren, Bildpfade auf lokale Assets abbilden, interne Links normalisieren, fehlende Inhalte behandeln, Metadaten bereitstellen – unabhängig vom Styling.

## 18. ContentRenderer

Komponenten: `Heading`, `Paragraph`, `RichText`, `Image`, `ImageGallery`, `List`, `Table`, `Button`, `Link`, `ContentSection`, `CardGrid`, `FAQ`, `CallToAction`, `FallbackBlock`.

Inhalte vollständig und in Originalreihenfolge. Unbekannte Blocktypen: generische Darstellung bzw. sicher bereinigtes HTML, protokollieren, nichts weglassen. Keine ungeprüften Skripte.

## 19. Navigation und Layout

Hauptnavigation aus `navigation.json`: Reihenfolge, Untermenüs, interne/externe Links, aktiver Zustand, Desktop + Mobile. Footer aus Navigationsdaten. Gemeinsames Layout: `RootLayout → Header/Navigation → Main/ContentRenderer → Footer`.

## 20. Design

Neutral, responsiv, lesbare Typografie, einheitliche Abstände, flexible Container, einheitliche Buttons/Links, grundlegende Barrierefreiheit. Originaldesign wird nicht reproduziert; Tailwind erleichtert die Individualisierung.

## 21. Assets

Lokale Bilder unter `public/assets/`, gültige Pfade, keine Abhängigkeit vom Originalserver, SVG/PNG/JPEG/WebP, Alt-Texte erhalten, fehlende Bilder nachvollziehbar behandeln, Duplikate vermeiden.

## 22. Frontend-Struktur

```text
generated-website/
├── app/{layout.tsx, globals.css, not-found.tsx, [[...slug]]/page.tsx}
├── components/layout/{Header, Navigation, MobileNavigation, Footer}.tsx
├── components/content/{ContentRenderer, Heading, Paragraph, ImageBlock, ListBlock, TableBlock, FallbackBlock, …}.tsx
├── lib/{content.ts, navigation.ts, routes.ts}
├── content/{manifest.json, navigation.json, pages/}
├── public/assets/
└── package.json, tsconfig.json, next.config.ts, README.md
```

## 23. Lokaler Betrieb

```bash
cd generated-website && npm install && npm run dev   # → http://localhost:3000
```

## 24. Erneuter Import

**Ein erneuter Content-Import darf das angepasste Frontend nicht überschreiben.** Getrennte Ebenen:

- **Content Layer:** Manifest, Navigation, Seitendaten, Bilder, Metadaten → verwaltete Verzeichnisse `content/` und `public/assets/`.
- **Presentation Layer:** Komponenten, Layouts, Tailwind, Designsystem, eigene Anpassungen → werden nie angefasst.

Workflow: neu crawlen → validieren → Content/Assets synchronisieren → neue/entfernte Seiten dokumentieren → Design unverändert.

## 25. Qualitätssicherung

Alle Seiten mit auflösbarer Route, Content-Dateien vorhanden, Schema-konform, Navigation/Footer geladen, interne Links gültig, Bilder vorhanden, keine Pfadkollisionen, nicht unterstützte Blöcke protokolliert, Build erfolgreich, Re-Import ohne Designverlust.

Tests: Unit (Loader, Routing), Komponenten, Integration (Import), Playwright, Linkprüfung, Produktions-Build.

## 26. Definition of Done

- [ ] Archiv importierbar und automatisch validiert
- [ ] vollständiges Next.js-Projekt mit dynamischem Routing
- [ ] alle Seiten lokal erreichbar, Navigation/Untermenüs/Footer funktionieren
- [ ] Inhalte in Originalreihenfolge gerendert, Bilder lokal
- [ ] neutrales, responsives Design
- [ ] `npm run dev` und Produktions-Build funktionieren
- [ ] erneuter Import möglich, Designanpassungen bleiben erhalten
- [ ] unabhängig vom Scraper
