# Content Schema v1.0

Die gemeinsame Schnittstelle zwischen **Scraper** (Produzent) und **Generator** (Konsument).
Maßgeblich sind die JSON-Schemas in [`schemas/v1/`](../schemas/v1). Dieses Dokument erklärt sie.
Ein vollständiges Beispiel liegt in [`examples/sample-website-source/`](../examples/sample-website-source).

## Archivstruktur

```text
website-source/
├── manifest.json            # manifest.schema.json  – Website + alle Seiten (verbindliche URL↔Datei-Zuordnung)
├── navigation.json          # navigation.schema.json – Menüs (main, footer, alle erkannten Menüs)
├── sitemap.json             # sitemap.schema.json   – Seitenbaum + interner Link-Graph
├── pages/<dir>/
│   ├── content.json         # page.schema.json      – Inhalte in Sections/Blocks
│   ├── content.md           # Markdown-Fassung (Referenz, nicht normativ)
│   ├── original.html        # gerendertes Original-HTML (Referenz/Fallback)
│   └── images.json          # images.schema.json (kind=page) – Bilder der Seite mit Zuordnung
├── assets/
│   ├── images/              # heruntergeladene Dateien: <sha256[:8]>-<name>.<ext>
│   └── images.json          # images.schema.json (kind=registry)
└── reports/
    ├── crawl-report.json    # report.schema.json (kind=crawl)
    ├── failed-urls.json     # report.schema.json (kind=failed-urls)
    ├── broken-links.json    # report.schema.json (kind=broken-links)
    └── missing-assets.json  # report.schema.json (kind=missing-assets)
```

Alle Dateireferenzen innerhalb des Archivs sind **relativ zum Archiv-Root** (z. B. `assets/images/1a2b3c4d-logo.svg`).

## Versionierung

Jede JSON-Datei trägt `"schemaVersion": "1.0"`. Der Generator lehnt Archive mit anderer Major-Version mit einer klaren Fehlermeldung ab. Neue optionale Felder erhöhen die Minor-Version, inkompatible Änderungen die Major-Version.

## Pfade und URLs

| Begriff | Beispiel | Regel |
|---|---|---|
| `originalUrl` | `https://Example.com/Leistungen/?utm_source=x#top` | so wie entdeckt |
| `finalUrl` | `https://example.com/leistungen/` | nach Weiterleitungen |
| `normalizedUrl` | `https://example.com/leistungen` | Host klein, Default-Port, Fragment und Tracking-Parameter entfernt, Query sortiert, kein Trailing-Slash |
| `path` | `/leistungen` | beginnt mit `/`, kein Trailing-Slash (außer `/`), `index.html`/`.html`/`.htm` entfernt, Groß-/Kleinschreibung bleibt |
| `dir` | `pages/leistungen` | lesbar (`[a-z0-9-]`), Startseite = `pages/index`, bei Kollision Suffix `-<hash6>` |

Seiten, die sich nur durch (inhaltlich relevante, mit `--keep-query` erlaubte) Query-Parameter unterscheiden, erhalten den Pfad `<pfad>/q-<slug-der-query>`.

**Interne Links** werden überall als Objekt mit `href` (Original), `path` (auflösbarer Pfad, ggf. mit `#fragment`) und `external: false` gespeichert. Externe Links haben `path: null`, `external: true`.

## Seite (`content.json`)

```json
{
  "schemaVersion": "1.0",
  "path": "/leistungen",
  "url": "https://example.com/leistungen",
  "title": "Unsere Leistungen",
  "meta": { "title": "...", "description": "...", "canonical": "...", "lang": "de", "h1": "...", "og": {}, "structuredData": [] },
  "breadcrumbs": [ /* navItem[] */ ],
  "sections": [
    { "id": "s1", "type": "hero", "blocks": [ /* block[] */ ], "source": { "tag": "section", "id": null, "classes": ["hero"] } }
  ]
}
```

**Reihenfolge ist verbindlich:** `sections` und `blocks` stehen in Dokumentreihenfolge.

### Section-Typen

`hero` · `content` · `cards` · `faq` · `testimonials` · `gallery` · `cta` · `form` · `generic`

Die Typen sind **Hinweise** für das Layout. Wird ein Bereich nicht sicher erkannt, ist er `generic`, die Inhalte bleiben vollständig in `blocks`.

### Rich Text (Inline-Knoten)

Fließtext ist ein Array von Inline-Knoten, damit Formatierungen und Links erhalten bleiben:

```json
[
  { "type": "text", "text": "Wir bieten " },
  { "type": "text", "text": "Webdesign", "marks": ["bold"] },
  { "type": "text", "text": " und " },
  { "type": "link", "href": "https://example.com/seo", "path": "/seo", "external": false, "children": [ { "type": "text", "text": "SEO" } ] },
  { "type": "break" }
]
```

Marks: `bold`, `italic`, `underline`, `strike`, `code`, `sub`, `sup`, `mark`.

### Blocktypen

| Typ | Felder |
|---|---|
| `heading` | `level` (1–6), `content` (Rich Text), `anchor` |
| `paragraph` | `content` |
| `list` | `ordered`, `items[]` mit `content` und optional `blocks` (verschachtelte Listen) |
| `table` | `caption`, `head[][]`, `rows[][]` – Zellen mit `content`, `header`, `colspan`, `rowspan` |
| `quote` | `blocks`, `cite` |
| `image` | `src` (lokal, `null` wenn nicht geladen), `originalSrc`, `alt`, `caption`, `width`, `height`, `link`, `role` |
| `gallery` | `images[]` (image-Blöcke) |
| `button` | `label`, `href`, `path`, `external`, `variant` |
| `embed` | `provider` (`youtube`/`vimeo`/`video`/`audio`/`map`/`iframe`), `url`, `title`, `poster` |
| `code` | `text`, `language` |
| `divider` | – |
| `card` | `blocks`, `link` – ein Element in Feature-/Service-/Testimonial-Grids |
| `accordion` | `items[]` mit `title` (Rich Text) und `blocks` – FAQs, Akkordeons, Tabs |
| `form` | `action`, `method`, `submitLabel`, `fields[]` – nur dokumentiert, nicht funktional |
| `html` | `html` (bereinigt: keine Skripte, Styles, Event-Handler), `text`, `reason` – **Fallback**, damit nichts verloren geht |

## Navigation (`navigation.json`)

```json
{
  "schemaVersion": "1.0",
  "main":   [ { "label": "Leistungen", "url": "https://example.com/leistungen", "path": "/leistungen", "external": false, "order": 1, "depth": 0, "type": "main", "children": [ ... ] } ],
  "footer": [ { "label": "Rechtliches", "url": null, "path": null, "external": false, "order": 0, "depth": 0, "type": "footer", "children": [ ... ] } ],
  "logo":   { "href": "https://example.com/", "path": "/", "external": false, "image": "assets/images/...", "alt": "Logo" },
  "cta":    [ ... ],
  "menus":  [ { "id": "menu-1", "type": "main", "selector": "header nav", "ambiguous": false, "pages": 12, "items": [ ... ] } ]
}
```

- Die Navigation stammt ausschließlich aus echten Navigationselementen im DOM, nie aus „allen Links“.
- Gruppenüberschriften ohne eigenen Link haben `url: null`, `path: null`.
- `ambiguous: true` kennzeichnet Menüs, deren Hierarchie nicht sicher bestimmbar war (sie werden flach so übernommen, wie gefunden).

## Manifest (`manifest.json`)

Listet jede exportierte Seite mit `path`, `title`, `originalUrl`, `finalUrl`, `normalizedUrl`, `canonical`, `aliases` (weitere Original-Pfade, z. B. für Redirects), `dir` und den Dateireferenzen `content`, `markdown`, `html`, `images`. **Jeder `path` ist eindeutig.**

## Validierung

```bash
python -m scraper validate ./outputs/example-source   # Scraper-Seite
npm run validate -- --source ./outputs/example-source  # Generator-Seite (im Ordner generator/)
```

Beide prüfen alle Dateien gegen `schemas/v1` sowie die Querverweise (Seiten-Dateien vorhanden, Pfade eindeutig, Bilder vorhanden).
