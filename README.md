# site-scraper – Website Scraper & Redesign Starter

Bestehende Websites inhaltlich möglichst vollständig erfassen und daraus automatisch ein lokal lauffähiges, redesignbares Next.js-Grundgerüst erzeugen.

```text
Website-URL ──► scraper/ (Python, Crawl4AI) ──► Content-Archiv (Schema v1.0) ──► generator/ (Node) ──► Next.js-Projekt ──► localhost:3000 ──► Redesign
```

| Modul | Aufgabe | Doku |
|---|---|---|
| [`scraper/`](scraper) | Crawling (Sitemaps, Links, JavaScript-Rendering), Navigation, Inhalte in Originalreihenfolge, Bilder, Metadaten, Prüfberichte | [scraper/README.md](scraper/README.md) |
| [`generator/`](generator) | Archiv validieren, Next.js-Projekt aus fester Vorlage erzeugen, Inhalte später neu importieren, ohne das Design zu überschreiben | [generator/README.md](generator/README.md) |
| [`schemas/v1/`](schemas/v1) | verbindliche Schnittstelle (JSON Schema) zwischen beiden Modulen | [docs/CONTENT-SCHEMA.md](docs/CONTENT-SCHEMA.md) |
| [`examples/`](examples) | Beispiel-Archiv, damit der Generator ohne echten Crawl testbar ist | |
| `outputs/` | erzeugte Archive und Websites (nicht versioniert) | |
| [`docs/`](docs) | Gesamtplan und Modulpläne | [docs/00-GESAMTPLAN.md](docs/00-GESAMTPLAN.md) |

## Schnellstart

Voraussetzungen: Python ≥ 3.11, Node ≥ 20.9.

Alle Befehle gelten für Linux, macOS und Windows gleich und werden im Projektordner ausgeführt. Unter Linux/macOS heißt Python vor dem Aktivieren der venv oft `python3`.

Einmalig einrichten:

```bash
python scripts/setup.py
```

Das Skript legt die Python-Umgebung `.venv/` im Projektordner an und installiert die Scraper-Abhängigkeiten in den getesteten Versionen aus `scraper/requirements-dev.txt`. Danach lädt es Chromium für das Browser-Rendering und installiert die Node-Pakete des Generators per `npm ci` nach `package-lock.json`.
Ein erneuter Aufruf schadet nicht. Mit `--no-browser` lässt du den Chromium-Download weg. Der Scraper läuft dann nur mit `--no-render`. Mit `--no-node` überspringst du den Generator-Teil, etwa solange Node noch nicht installiert ist.

Für Variante B die Umgebung aktivieren (`redesign-tool.py` findet `.venv` auch ohne):

```bash
source .venv/bin/activate        # Linux/macOS
.\.venv\Scripts\Activate.ps1     # Windows (PowerShell)
```

**Abhängigkeiten:**

| Datei | Rolle |
|---|---|
| `scraper/pyproject.toml` | Paketdefinition mit Mindestversionen |
| `scraper/requirements.txt` | exakt getestete Versionen |
| `scraper/requirements-dev.txt` | dasselbe plus pytest |
| `generator/package-lock.json` | Node-Gegenstück zu `requirements.txt` |

Versionen aktualisieren: `pip install -U <paket>` in der venv, Tests laufen lassen, dann die Pins in `requirements.txt` anpassen. Die venv selbst wird nie committet, sie steht in `.gitignore`.

**Variante A – Gesamtskript:**

#### 1. Scraper und Generator in einem Befehl

```bash
python redesign-tool.py create https://example.com --max-pages 200
```

Liegt die Website in einem Unterordner eines fremden Hosts, mit `--scope` nur diesen Ordner erfassen. Er wird zur Wurzel `/`, alles andere auf dem Host gilt als extern:

```bash
python redesign-tool.py create https://cms.sachsen.schule/fsamzeisigwald/ --scope /fsamzeisigwald/
```

Ohne `--scope` gilt das Verzeichnis der Start-URL (bis zum letzten `/`) als Bereich. Siehe `--scope` in [scraper/README.md](scraper/README.md#benutzung).

#### 2. Website lokal starten

```bash
cd outputs/example-com-website
npm install
npm run dev
```

**Variante B – Module einzeln:**

#### 1. Scraper – Website als Archiv erfassen

Die venv muss aktiviert sein (siehe oben).

```bash
python -m scraper --url https://example.com --output ./outputs/example-source
```

`--scope` funktioniert hier genauso:

```bash
python -m scraper --url https://cms.sachsen.schule/fsamzeisigwald/ --scope /fsamzeisigwald/ --output ./outputs/fsamzeisigwald-source
```

#### 2. Generator – Next.js-Projekt aus dem Archiv erzeugen

```bash
cd generator
npm run generate -- --source ../outputs/example-source --output ../outputs/example-website
```

#### 3. Website lokal starten

```bash
cd ../outputs/example-website
npm install
npm run dev
```

Danach ist die Website unter http://localhost:3000 erreichbar.

**Inhalte später aktualisieren:** `python redesign-tool.py create …` einfach erneut ausführen oder `npm run sync` im Generator. Ersetzt werden nur `content/` und `public/assets/`. Komponenten, Styles und eigene Dateien bleiben erhalten.

## Was erfasst wird

- **Seiten:** über `sitemap.xml` (auch Indizes und gz), `robots.txt` und rekursive interne Links, auch per JavaScript erzeugte.
  - URL-Normalisierung entfernt Tracking-Parameter und Fragmente.
  - Weiterleitungen, Canonical-URLs und Duplikate werden als Aliases geführt.
- **Navigation:** nur echte Menüs aus dem DOM, nie „alle Links“.
  - Hauptmenü mit Dropdowns und Mega-Menü-Gruppen, Footer-Spalten, Logo, CTA, Breadcrumbs.
  - Ein Mobile-Menü wird nur übernommen, wenn es zusätzliche Einträge hat.
- **Inhalte:** Sections (`hero`, `cards`, `faq`, `testimonials`, `gallery`, `cta`, `form`, `content`, `generic`) mit Blöcken in Dokumentreihenfolge: Überschriften, Rich Text (fett, kursiv, Links), Listen, Tabellen, Zitate, Bilder, Galerien, Buttons, Karten, Akkordeons, Formulare, Embeds, Code.
  - Nicht zuordenbare Inhalte bleiben als bereinigter HTML-Fallback erhalten.
- **Bilder:** `img`, `picture`/`srcset` (größte Variante), Lazy Loading, CSS-Hintergründe, Inline-SVG, Logo und OG-Bild.
  - Gespeichert lokal im Originalformat, dedupliziert und der jeweiligen Seite, Section und dem Block zugeordnet.
- **Metadaten:** Title, Description, Canonical, Sprache, H1, Open Graph, JSON-LD.
- **Berichte:** `reports/crawl-report.json` mit dem Status `complete`, `limited` oder `errors`. Dazu Listen fehlgeschlagener URLs, defekter Links und fehlender Bilder.

## Tests

Jeweils aus dem Projektordner:

```bash
cd scraper; python -m pytest
```

```bash
cd generator; npm test
```

```bash
cd generator; npm run test:e2e
```

Gesamttest (Test-Website → Scraper → Generator → Build → Browser, benötigt Playwright, siehe [generator/README.md](generator/README.md)):

```bash
python scripts/e2e-pipeline.py
```

| Befehl | Was er prüft |
|---|---|
| `pytest` | Unit-Tests und Crawl einer lokalen Test-Website, statisch und mit Browser |
| `npm test` | Validierung, Import/Sync, Checks, Loader, Komponenten |
| `npm run test:e2e` | Beispiel-Archiv → Build → Playwright |
| `scripts/e2e-pipeline.py` | Test-Website → Scraper → Generator → Build → Playwright |

## Grenzen (v1)

Kein pixelgenaues Kopieren des Designs, kein Klonen von CSS/JS, keine Backend-, Shop- oder Login-Funktionen, keine Umgehung von Zugriffsbeschränkungen, keine KI-Umformulierung von Texten, kein Download großer Videos. Formulare werden dokumentiert, aber nicht angebunden.

> **Rechtlicher Hinweis:** Nur Websites erfassen, für die die nötigen Rechte bestehen, z. B. die eigene Website oder die eines Kunden mit dessen Zustimmung. Texte und Bilder sind in der Regel urheberrechtlich geschützt. `robots.txt` wird beachtet.
