/**
 * Content import / sync: copies an archive into the managed directories of a generated project.
 * Only `content/` and `public/assets/` are touched – components, styles and other files stay as they are.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { readJson, validateArchive, type Manifest } from "./archive.js";

export const MARKER_FILE = ".redesign-tool.json";
export const MANAGED_DIRS = ["content", "public/assets"] as const;
export const TOOL_VERSION = "0.1.0";

export type ImportReport = {
  schemaVersion: string;
  importedAt: string;
  source: string;
  sourceUrl: string;
  pages: number;
  assets: number;
  added: string[];
  removed: string[];
  changed: string[];
  unchanged: number;
};

export class ImportError extends Error {
  constructor(message: string, public details: string[] = []) {
    super(message);
  }
}

/** "assets/images/x.png" (archive-relative) -> "/assets/images/x.png" (public URL). */
export function rewriteAssetPaths<T>(value: T): T {
  if (typeof value === "string") {
    return (value.startsWith("assets/") ? "/" + value : value) as T;
  }
  if (Array.isArray(value)) return value.map(rewriteAssetPaths) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value)) {
      // only rewrite reference fields, never texts
      out[key] = ["src", "image", "file"].includes(key) || typeof child === "object" ? rewriteAssetPaths(child) : child;
    }
    return out as T;
  }
  return value;
}

function hash(content: string): string {
  return crypto.createHash("sha256").update(content).digest("hex");
}

function pageHashes(contentRoot: string): Map<string, string> {
  const hashes = new Map<string, string>();
  const manifestFile = path.join(contentRoot, "manifest.json");
  if (!fs.existsSync(manifestFile)) return hashes;
  try {
    const manifest = readJson<Manifest>(manifestFile);
    for (const page of manifest.pages) {
      const file = path.join(contentRoot, page.content);
      if (fs.existsSync(file)) hashes.set(page.path, hash(fs.readFileSync(file, "utf8")));
    }
  } catch {
    // previous content unreadable -> everything counts as added
  }
  return hashes;
}

function writeJson(file: string, data: unknown) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

export type ImportOptions = { skipValidation?: boolean; now?: Date };

export function importContent(archive: string, project: string, options: ImportOptions = {}): ImportReport {
  archive = path.resolve(archive);
  project = path.resolve(project);
  const validation = options.skipValidation ? { ok: true, errors: [], manifest: readJson<Manifest>(path.join(archive, "manifest.json")) } : validateArchive(archive);
  if (!validation.ok || !validation.manifest) {
    throw new ImportError(`Archive ${archive} is not a valid Content Archive v1.0`, validation.errors);
  }
  const manifest = validation.manifest;
  const contentDir = path.join(project, "content");
  const assetsDir = path.join(project, "public", "assets");
  const previous = pageHashes(contentDir);

  // 1. stage the new content next to the old one
  const stage = path.join(project, `.content-import-${process.pid}`);
  fs.rmSync(stage, { recursive: true, force: true });
  const stageContent = path.join(stage, "content");
  const stageAssets = path.join(stage, "assets");
  try {
    for (const file of ["manifest.json", "navigation.json", "sitemap.json"]) {
      const src = path.join(archive, file);
      if (fs.existsSync(src)) writeJson(path.join(stageContent, file), rewriteAssetPaths(readJson(src)));
    }
    const hashes = new Map<string, string>();
    for (const page of manifest.pages) {
      const data = rewriteAssetPaths(readJson(path.join(archive, page.content)));
      const serialized = JSON.stringify(data, null, 2) + "\n";
      fs.mkdirSync(path.dirname(path.join(stageContent, page.content)), { recursive: true });
      fs.writeFileSync(path.join(stageContent, page.content), serialized);
      hashes.set(page.path, hash(serialized));
      if (page.images && fs.existsSync(path.join(archive, page.images))) {
        writeJson(path.join(stageContent, page.images), rewriteAssetPaths(readJson(path.join(archive, page.images))));
      }
    }
    let assetCount = 0;
    const archiveImages = path.join(archive, "assets", "images");
    fs.mkdirSync(path.join(stageAssets, "images"), { recursive: true });
    if (fs.existsSync(archiveImages)) {
      for (const name of fs.readdirSync(archiveImages)) {
        fs.copyFileSync(path.join(archiveImages, name), path.join(stageAssets, "images", name));
        assetCount++;
      }
    }
    fs.writeFileSync(
      path.join(stageContent, "README.md"),
      "Dieser Ordner wird vom Generator verwaltet (`npm run sync`) und bei jedem Content-Import ersetzt.\n" +
        "Inhalte hier nicht von Hand ändern – Designänderungen gehören in `app/`, `components/` und `lib/`.\n",
    );

    const added = [...hashes.keys()].filter((p) => !previous.has(p));
    const removed = [...previous.keys()].filter((p) => !hashes.has(p));
    const changed = [...hashes.keys()].filter((p) => previous.has(p) && previous.get(p) !== hashes.get(p));
    const report: ImportReport = {
      schemaVersion: manifest.schemaVersion,
      importedAt: (options.now ?? new Date()).toISOString(),
      source: archive,
      sourceUrl: manifest.sourceUrl,
      pages: manifest.pages.length,
      assets: assetCount,
      added,
      removed,
      changed,
      unchanged: hashes.size - added.length - changed.length,
    };
    writeJson(path.join(stageContent, "import-report.json"), report);

    // 2. swap the managed directories (nothing else is touched)
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(assetsDir, { recursive: true, force: true });
    fs.mkdirSync(path.dirname(assetsDir), { recursive: true });
    fs.renameSync(stageContent, contentDir);
    fs.renameSync(stageAssets, assetsDir);

    writeJson(path.join(project, MARKER_FILE), {
      tool: "site-generator",
      version: TOOL_VERSION,
      schemaVersion: manifest.schemaVersion,
      managed: MANAGED_DIRS,
      note: "Only the managed directories are replaced by `npm run sync`. Everything else belongs to the redesign.",
      lastImport: { at: report.importedAt, source: archive, sourceUrl: manifest.sourceUrl, pages: report.pages },
    });
    return report;
  } finally {
    fs.rmSync(stage, { recursive: true, force: true });
  }
}
