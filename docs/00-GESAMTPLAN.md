# Gesamtprojektplan: Website Scraper & Redesign Starter

**Projekt:** Website Content Extraction & Redesign Framework
**Architektur:** Zwei unabhängige Module mit gemeinsamer Datenschnittstelle
**Ziel:** Bestehende Websites inhaltlich möglichst vollständig erfassen und daraus automatisch ein lokal lauffähiges, redesignbares Website-Grundgerüst erstellen.

Detailpläne der Module:

- [01-SCRAPER-PLAN.md](01-SCRAPER-PLAN.md) – Teil 1, Abschnitte 2–11
- [02-WEBSITE-GENERATOR-PLAN.md](02-WEBSITE-GENERATOR-PLAN.md) – Teil 2, Abschnitte 13–26
- [CONTENT-SCHEMA.md](CONTENT-SCHEMA.md) – gemeinsame Schnittstelle (Abschnitt 12, konkretisiert)

---

# 1. Projektübersicht

## 1.1 Projektziel

Entwicklung eines modularen Systems, das bestehende Websites automatisiert analysiert, deren Inhalte und Struktur archiviert und daraus ein funktionsfähiges Frontend-Grundgerüst erzeugt.

**Teil 1 – Website Scraper:** Crawling, vollständige Inhaltsextraktion, Navigationserkennung, Bilddownloads und strukturierte Speicherung sämtlicher Daten.

**Teil 2 – Website Grundgerüst Generator:** Verarbeitung der exportierten Daten und automatische Erstellung einer lokal lauffähigen Next.js-Website mit funktionierender Navigation und allen erfassten Seiteninhalten.

## 1.2 Gesamtworkflow

```text
WEBSITE-URL
    │
    ▼
┌─────────────────────────────┐
│ TEIL 1: WEBSITE SCRAPER     │
│ • Unterseiten erkennen      │
│ • Navigation extrahieren    │
│ • Inhalte erfassen          │
│ • Bilder herunterladen      │
│ • Daten strukturieren       │
│ • Vollständigkeit prüfen    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ STANDARDISIERTES ARCHIV     │
│ • manifest.json             │
│ • navigation.json           │
│ • sitemap.json              │
│ • pages/*.json, pages/*.md  │
│ • assets/                   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ TEIL 2: WEBSITE GENERATOR   │
│ • Archiv validieren         │
│ • Next.js vorbereiten       │
│ • Dynamische Routen         │
│ • Navigation einbinden      │
│ • Content rendern           │
│ • Bilder einbinden          │
└──────────────┬──────────────┘
               ▼
       GENERATED WEBSITE → localhost:3000 → INDIVIDUELLES REDESIGN
```

## 1.3 Grundprinzipien

- Originalgetreue Übernahme aller erfolgreich erfassten Website-Inhalte.
- Möglichst vollständige Erfassung öffentlich erreichbarer Unterseiten.
- Erhaltung der Navigation, Seitenhierarchie und Verlinkungen.
- Erhaltung der ursprünglichen Reihenfolge aller Inhaltsbereiche.
- Lokale Speicherung der Bilder und relevanten Medien.
- Klare Trennung von Inhalt, Routing und Design.
- Keine Abhängigkeit des Scrapers von Next.js.
- Keine Abhängigkeit des Generators vom ursprünglichen Website-Quellcode.
- Keine KI-generierten Zusammenfassungen oder Umformulierungen der Originaltexte.
- Das ursprüngliche Design muss nicht reproduziert werden.
- Beide Module sollen unabhängig ausführbar, testbar und erweiterbar sein.

---

# 12. Gemeinsame Schnittstelle – Content Schema v1.0

Beide Module verwenden dasselbe Datenformat. Der Scraper produziert, der Generator konsumiert. Beide dürfen unabhängig weiterentwickelt werden, solange die Schnittstelle kompatibel bleibt.

Verbindliche Regeln:

1. Jede exportierte Seite besitzt einen eindeutigen normalisierten Pfad.
2. Jeder Inhalt wird einer Seite zugeordnet.
3. Die Reihenfolge von Sections und Blocks bleibt erhalten.
4. Assets besitzen stabile lokale Referenzen.
5. Interne Links werden als auflösbare Pfade gespeichert.
6. Nicht erkannte Inhalte dürfen nicht stillschweigend verworfen werden.
7. Das Schema besitzt eine Versionsnummer.
8. Der Generator prüft die Schema-Kompatibilität vor dem Import.
9. Ungültige Daten führen zu nachvollziehbaren Fehlermeldungen.

**Architekturentscheidung:** Die Content-Dateien sind die zentrale Datenquelle für das Frontend. Das ursprüngliche HTML dient als Referenz und Fallback, nicht als technische Basis des neuen Designs.

Konkrete Spezifikation: [CONTENT-SCHEMA.md](CONTENT-SCHEMA.md).

---

# 27. Gesamtprojektstruktur

```text
site-scraper/
├── scraper/        # Crawling und Export (Python)
├── generator/      # Erstellung/Aktualisierung der Next.js-Website (Node)
│   └── templates/nextjs-starter/
├── schemas/v1/     # verbindliche Datenstrukturen beider Module
├── examples/       # Beispieldaten (Generator ohne echten Scrape testbar)
├── outputs/        # generierte Archive und Websites (gitignored)
├── docs/           # Architektur- und Entwicklungsdokumentation
└── README.md
```

# 28. Bedienung

```bash
python -m scraper --url https://example.com --output ./outputs/example-source
```

```bash
npm run generate -- --source ./outputs/example-source --output ./outputs/example-website
```

```bash
cd outputs/example-website && npm install && npm run dev
```

Optional später: `redesign-tool create https://example.com` führt beide Schritte aus. Die Kernmodule bleiben unabhängig nutzbar.

# 29. Entwicklungsreihenfolge

- **Phase 0 – Gemeinsames Datenmodell:** Schema v1.0, Manifest, Navigation, Blocktypen, Asset-Referenzen, URL-/Routing-Regeln, Beispiel-Archiv, Validierung.
- **Phase 1 – Scraper MVP:** URL-Discovery, Sitemaps, rekursives Crawling, HTML/Markdown-Export, Navigation, Bilder, JSON, Fehlerberichte.
- **Phase 2 – Scraper vervollständigen:** verschachtelte Navigation, dynamische Inhalte, Abschnittserkennung, Bildzuordnung, URL-Kollisionen, Vollständigkeitsprüfung.
- **Phase 3 – Generator MVP:** Next.js-Starter, Import, Validierung, dynamisches Routing, ContentRenderer, Navigation/Footer, Bilder.
- **Phase 4 – Generator vervollständigen:** weitere Blocktypen, Responsive Layout, Mobile Navigation, Fallback-Rendering, Linkprüfung, erneuter Import ohne Designverlust.
- **Phase 5 – Integration und E2E-Tests:** Scrape-to-localhost-Workflow prüfen, Berichte zusammenführen, Bedienung dokumentieren.

# 30. Akzeptanzkriterien

**Content-Erfassung:** entdeckte öffentliche Seiten innerhalb der Grenzen verarbeitet; Navigation/Struktur originalgetreu; Texte nicht umformuliert; Reihenfolge erhalten; Bilder lokal; Fehlendes dokumentiert.

**Technische Struktur:** Scraper und Generator unabhängig; versionierte Schnittstelle; Archiv ohne Generator nutzbar; Generator mit Beispieldaten testbar.

**Generiertes Frontend:** vollständige Next.js-Struktur; alle exportierten Seiten mit lokalen Routen; Navigation und Links funktionieren; Bilder und Texte eingebunden; responsiv und lokal startbar; Redesign ohne Änderung der Originaldaten möglich.

**Wartbarkeit:** wiederverwendbare Komponenten; keine individuell programmierten Seiten; erneuter Scrape aktualisiert Inhalte; Designänderungen werden beim Import nicht überschrieben.

# 31. Bewusst ausgeschlossen (v1)

Pixelgenaue Reproduktion, Klonen von CSS/JS, Backend-Rekonstruktion, Shop/Checkout, Login-Inhalte, Umgehung von Zugriffsbeschränkungen, KI-Redesigns, automatische Texterstellung, Hosting/Deployment, Download großer Video-Bibliotheken.

# 32. Architektur – drei Schichten

1. **Extraction Layer** – Scraper wandelt die Website in ein strukturiertes Datenformat um.
2. **Content Layer** – versioniertes Archiv mit Inhalten, Navigation, Assets, Metadaten.
3. **Presentation Layer** – Generator / Next.js-Projekt stellt die Daten unabhängig vom Originaldesign dar.

**Zentrale Regel:** Jede Schicht muss unabhängig von den anderen weiterentwickelt werden können.

# 33. Endergebnis

**Website auswählen → Inhalte und Navigation erfassen → Bilder lokal sichern → Content-Archiv erstellen → Next.js-Grundgerüst generieren → Website auf localhost öffnen → Individuelles Redesign umsetzen.**
