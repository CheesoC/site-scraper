# Teil 1 – Website Scraper

## 2. Ziel

Der Scraper erfasst eine Website anhand ihrer URL und erstellt ein möglichst vollständiges, strukturiertes Content-Archiv, mit dem die Website später mit einem anderen Frontend neu aufgebaut werden kann. Er funktioniert vollständig unabhängig vom Generator.

**Eingabe:** Website-URL. Optional: maximale Crawl-Tiefe, maximale Seitenanzahl, erlaubte Domains/Subdomains, Anfragegeschwindigkeit und Parallelität, Browser-Rendering an/aus, Ausgabeverzeichnis, Bilddownload an/aus.

**Ausgabe:** Standardisiertes Archiv mit Navigation, Unterseiten, Texten, Bildern, Links, Metadaten und Prüfberichten.

## 3. Discovery und Crawling

- **3.1 Sitemaps:** `/sitemap.xml`, Sitemap-URLs aus `robots.txt`, Sitemap-Indizes, weitere referenzierte Sitemaps.
- **3.2 Rekursives Crawling:** alle internen Unterseiten über Hauptnavigation, Footer und Inhalte; mehrstufige Pfade; JS-generierte Links soweit möglich; keine Duplikate; fehlerhafte URLs dokumentieren; konfigurierbare Grenzen.
- **3.3 URL-Normalisierung:** Fragmente und Tracking-Parameter erzeugen keine Duplikate; inhaltlich relevante Query-Parameter bleiben. Pro Seite: ursprüngliche URL, finale URL, normalisierte URL, lokaler Pfad, Canonical-URL.
- **3.4 JavaScript-Websites:** Rendering mit Playwright; Lazy Loading, dynamische Bereiche, öffentlich zugängliche Akkordeons/Tabs, Scroll-Nachladung. Keine Umgehung von Logins oder Schutzmechanismen.
- **3.5 Regeln:** `robots.txt` beachten, angemessene Intervalle und Timeouts, begrenzte Wiederholungen, keine fremden Websites mitcrawlen.

## 4. Navigation und Seitenhierarchie

Zu erfassen: Hauptnavigation, Dropdowns, verschachtelte Untermenüs, Mobile Navigation (falls zusätzliche Einträge), Footer-Navigation, Logo-Links, Navigations-CTAs, Breadcrumbs.

Pro Eintrag: Beschriftung, ursprüngliche URL, normalisierter Pfad, Reihenfolge, Eltern-Kind-Beziehung, Tiefe, intern/extern, Navigationstyp.

**Wichtig:** Die Navigation wird **nicht** aus allen gefundenen Links generiert, sondern aus der DOM-Struktur (`<nav>`, `<header>`, `<footer>`, verschachtelte Listen, ARIA-Attribute). Mehrdeutige Strukturen werden gekennzeichnet, keine erfundenen Hierarchien.

Ausgabe: `navigation.json` mit `main`, `footer`, … (siehe [CONTENT-SCHEMA.md](CONTENT-SCHEMA.md)).

## 5. Inhaltsextraktion

- **Texte:** H1–H6, Absätze, fett/kursiv, Listen, Tabellen, Zitate, Beschriftungen, Kontaktinfos, Buttons/CTAs, interne und externe Links. Inline-Formatierungen und Links gehen nicht verloren.
- **Bereiche:** Hero, Content-Sections, Feature-Grids, Service-Karten, Testimonials, FAQs, Akkordeons, Galerien, CTAs, sonstige wiederkehrende Elemente.
- **Reihenfolge** ist verbindlich und im Frontend reproduzierbar.
- **Technik:** regelbasiert über DOM, einheitliches Datenmodell; Unklassifizierbares bleibt als generischer Block bzw. bereinigtes HTML erhalten. **Kein Informationsverlust.**

## 6. Bilder und Medien

- Erkennung: `<img>`, `picture`, `srcset`, Lazy-Loading, Logos, SVG, relevante CSS-Hintergrundbilder, Galerien.
- Speicherung: Originalformat, keine Komprimierung, Duplikaterkennung, eindeutige Namen, Größenlimits, nur sichere URLs, Fehler dokumentieren.
- Zuordnung: Original-URL, lokaler Pfad, Alt-Text, Seite, Inhaltsblock, Reihenfolge, Bildunterschrift.
- Videos/Embeds: nur URL und Einbettungsinformationen (kein Download in v1).

## 7. Metadaten

Seitentitel, Meta-Description, Canonical, Sprache, H1, Open Graph (Titel, Beschreibung, Bild), strukturierte Daten – getrennt von den sichtbaren Inhalten.

## 8. Ausgabe

```text
website-source/
├── manifest.json
├── navigation.json
├── sitemap.json
├── pages/<seite>/{content.json, content.md, original.html, images.json}
├── assets/{images/, images.json}
└── reports/{crawl-report.json, failed-urls.json, missing-assets.json, broken-links.json}
```

Verzeichnisnamen sind lesbar und bei Kollisionen eindeutig. Die verbindliche Zuordnung URL ↔ Datei erfolgt über das Manifest.

## 9. Qualitätssicherung

Abschlussbericht mit: entdeckten URLs, exportierten Seiten, Fehlschlägen, Duplikaten, fehlenden Bildern, defekten internen Links, unvollständigen Content-Dateien, Navigationseinträgen ohne Seite, Rendering-Fehlern, nicht unterstützten Bereichen. Der Bericht zeigt, ob der Crawl vollständig oder durch Limits/Fehler eingeschränkt war.

## 10. Stack und Architektur

Python · Crawl4AI · Playwright · BeautifulSoup · httpx · asyncio · JSON/Markdown/HTML · Pydantic + JSON Schema · pytest.

Komponenten (einzeln testbar): `URLDiscovery`, `URLNormalizer`, `PageCrawler`, `NavigationExtractor`, `ContentExtractor`, `AssetDownloader`, `ContentExporter`, `CrawlValidator`.

## 11. Definition of Done

- [ ] Ziel-URL als Eingabe
- [ ] Sitemaps und interne Links zur Erkennung
- [ ] Crawling innerhalb der Grenzen
- [ ] keine doppelten URLs
- [ ] Navigation und Untermenüs strukturiert exportiert
- [ ] Originaltexte vollständig, Reihenfolge erhalten
- [ ] Bilder lokal gespeichert und zugeordnet
- [ ] interne Links und Metadaten erhalten
- [ ] einheitliches Schema
- [ ] Fehlschläge dokumentiert
- [ ] ohne Generator ausführbar
- [ ] Archiv automatisiert validierbar
