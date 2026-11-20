/**
 * Content loader: the only place that reads the imported Content Archive (content/).
 * Components never touch the files directly, so the design can change without touching data handling.
 */
import fs from "node:fs";
import path from "node:path";
import { cache } from "react";
import type { z } from "zod";
import { normalizePath } from "./routes";
import {
  manifestSchema,
  navigationSchema,
  pageSchema,
  type Manifest,
  type ManifestPage,
  type Navigation,
  type Page,
} from "./schema";

export class ContentError extends Error {}

export function contentDir(): string {
  return process.env.CONTENT_DIR ?? path.join(process.cwd(), "content");
}

/** Path of a file inside the content directory (statically scoped to ./content for Next.js tracing). */
function contentFile(file: string): string {
  return process.env.CONTENT_DIR ? path.join(process.env.CONTENT_DIR, file) : path.join(process.cwd(), "content", file);
}

function readJson<T>(file: string, schema: z.ZodType<T>): T {
  const full = contentFile(file);
  let raw: unknown;
  try {
    raw = JSON.parse(fs.readFileSync(full, "utf8"));
  } catch (error) {
    throw new ContentError(`Content file ${file} could not be read: ${(error as Error).message}`);
  }
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    const details = parsed.error.issues
      .slice(0, 5)
      .map((issue) => `${issue.path.join("/") || "(root)"}: ${issue.message}`)
      .join("; ");
    throw new ContentError(`Content file ${file} does not match Content Schema v1: ${details}`);
  }
  return parsed.data;
}

export const getManifest = cache((): Manifest => readJson("manifest.json", manifestSchema));

export const getNavigation = cache((): Navigation => {
  if (!fs.existsSync(contentFile("navigation.json"))) {
    return { schemaVersion: "1.0", main: [], footer: [], logo: null, cta: [], menus: [] };
  }
  return readJson("navigation.json", navigationSchema);
});

const pageIndex = cache((): Map<string, ManifestPage> => {
  const index = new Map<string, ManifestPage>();
  for (const page of getManifest().pages) {
    index.set(normalizePath(page.path), page);
  }
  return index;
});

/** All routes of the site (for generateStaticParams and checks). */
export function getAllPaths(): string[] {
  return [...pageIndex().keys()];
}

export function findPage(slugOrPath: string | string[] | undefined): ManifestPage | undefined {
  return pageIndex().get(normalizePath(slugOrPath));
}

/** Load and validate a page. Returns undefined for unknown routes (-> 404). */
export const getPage = cache((slugOrPath: string): Page | undefined => {
  const entry = findPage(slugOrPath);
  if (!entry) return undefined;
  const page = readJson(entry.content, pageSchema);
  for (const section of page.sections) {
    for (const block of section.blocks) {
      if (block.type === "unknown") {
        console.warn(`[content] ${page.path}: unsupported block type "${block.originalType}" rendered with FallbackBlock`);
      }
    }
  }
  return page;
});

export function getSiteName(): string {
  const manifest = getManifest();
  return manifest.site?.name || new URL(manifest.sourceUrl).hostname;
}

export function getSiteLang(): string {
  return getManifest().site?.lang || "de";
}
