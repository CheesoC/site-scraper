# Scraper (Teil 1)

Erfasst eine Website anhand ihrer URL als **Content-Archiv** nach [Content Schema v1.0](../docs/CONTENT-SCHEMA.md).
Erfasst werden Seiten, Navigation, Inhalte in Originalreihenfolge, Bilder und Metadaten.
Der Scraper hängt nicht vom Generator ab.

## Installation

Python ≥ 3.11:

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -e "./scraper[dev]"
```

```bash
playwright install chromium
```

Der letzte Befehl wird nur für das Browser-Rendering gebraucht, den Standardmodus. Ohne Browser läuft der Scraper mit `--no-render`.

## Benutzung

```bash
python -m scraper --url https://example.com --output ./outputs/example-source
```

| Option | Bedeutung |
|---|---|
| `--max-depth N` | maximale Link-Tiefe ab Startseite (Standard 10) |
| `--max-pages N` | maximale Anzahl Seitenabrufe (Standard 500) |
| `--allow-domain D` | zusätzliche (Sub-)Domain, z. B. `blog.example.com` oder `*.example.com` (mehrfach möglich) |
| `--concurrency N` / `--delay S` | parallele Abrufe / Mindestabstand pro Abruf. Ein `Crawl-delay` in robots.txt hat Vorrang und setzt die Parallelität auf 1 |
| `--timeout S` / `--retries N` | Timeout pro Abruf / Wiederholungen bei 429, 5xx und Timeouts |
| `--no-render` | kein Browser, nur statisches HTML per HTTP (schnell, aber ohne JavaScript-Inhalte) |
| `--no-images` | keine Bilder herunterladen. Die Original-URLs bleiben im Archiv |
| `--no-sitemap` | Sitemaps ignorieren |
| `--no-html` | `original.html` nicht speichern |
| `--drop-query` | alle Query-Parameter verwerfen. Standard: nur Tracking-Parameter wie `utm_*` oder `fbclid` werden entfernt |
| `--max-asset-mb N` | Größenlimit pro Bild |
| `-v` | ausführliches Logging |

Ein Archiv prüfen:

```bash
python -m scraper validate ./outputs/example-source
```

## Ablauf

1. **URLDiscovery** (`discovery.py`) liest `robots.txt` (Regeln, `Crawl-delay`, Sitemap-Einträge). Dazu kommen `/sitemap.xml`, Sitemap-Indizes, gz-komprimierte und Text-Sitemaps.
2. **PageCrawler** (`crawler.py`) crawlt per Breitensuche ab der Start-URL und den Sitemap-URLs. Er hält sich an Tiefe, Seitenlimit, Domains und robots.txt. Duplikate erkennt er über den normalisierten Pfad, Weiterleitungen, Canonical-Links und Query-Varianten mit gleichem Inhalt.
3. **Fetcher** (`fetchers.py`) rendert die Seiten:
   - Crawl4AI/Playwright scrollt für Lazy Loading, öffnet `<details>` und markiert berechnete CSS-Hintergrundbilder.
   - Alternativ holt httpx die Seiten ohne JavaScript.
4. **URLNormalizer** (`urls.py`) erzeugt normalisierte URLs und Seitenpfade (`/leistungen/seo`). Daraus macht er lesbare, kollisionsfreie Verzeichnisse.
5. **NavigationExtractor** (`navigation.py`) liest echte Navigation aus dem DOM: `header`, `nav`, `footer`, verschachtelte Listen, Mega-Menü-Gruppen, Logo, CTA und Breadcrumbs (auch aus JSON-LD).
   - Menüs ohne erkennbare Listenstruktur mit Dropdown-Elementen bekommen `ambiguous: true`.
   - Über alle Seiten hinweg gewinnt die häufigste Variante.
   - Ein Mobile-Menü bleibt nur erhalten, wenn es zusätzliche Einträge enthält.
6. **ContentExtractor** (`content.py`) bestimmt den Hauptbereich und zerlegt ihn in Sections (`hero`, `cards`, `faq`, …) und Blöcke in Dokumentreihenfolge. Fett, kursiv und Links bleiben als Rich Text erhalten. Nicht zuordenbare Elemente werden zu bereinigten `html`-Fallback-Blöcken (`sanitize.py`).
7. **AssetDownloader** (`assets.py`) lädt Bilder in Originalqualität herunter: `srcset` (größte Variante), Lazy-Attribute, `picture`, CSS-Hintergründe, Inline-SVG, Data-URIs, Logo und OG-Bild.
   - Gleiche Dateien werden über SHA-256 nur einmal gespeichert.
   - Es gelten ein Größenlimit, eine Typprüfung und keine privaten Adressen, außer die Website selbst ist lokal.
8. **ContentExporter** (`exporter.py`) schreibt das Archiv und löst alle internen Links auf exportierte Pfade auf. Für jede Seite entsteht `content.md` (`markdown.py`).
9. **CrawlValidator** (`validator.py`) erstellt `reports/*.json` mit dem Status `complete`, `limited` oder `errors` und prüft das Archiv gegen `schemas/v1`.

## Tests

```bash
cd scraper && pytest
```

Die End-to-End-Tests crawlen eine lokale Test-Website (`tests/fixtures/site`, gestartet über `tests/fixture_server.py`). Die Seite enthält:
- Weiterleitung, 404 und robots.txt-Sperre
- verschachteltes Menü und eine Seite, die nur in der Sitemap steht
- Lazy Images, FAQ, Formular und einen per JavaScript erzeugten Link

Der Browser-Test läuft nur, wenn Chromium für Playwright installiert ist.

Die Test-Website lässt sich auch manuell starten:

```bash
python scraper/tests/fixture_server.py 8765
```

## Hinweise

- Erfasst werden nur öffentlich erreichbare Inhalte. Logins, Paywalls und Bot-Schutz werden nicht umgangen.
- Bitte nur Websites crawlen, für die du die Nutzungsrechte hast. Inhalte und Bilder sind in der Regel urheberrechtlich geschützt.
- Eine vollständige Erfassung jeder existierenden Seite ist nicht garantierbar. Was nicht erfasst wurde, steht im Bericht: Limits, Fehler, robots.txt, nicht verlinkte Seiten.
