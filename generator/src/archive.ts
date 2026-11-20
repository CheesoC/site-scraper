/** Validation of a Content Archive against Content Schema v1 (Ajv) plus cross-reference checks. */
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import type { ErrorObject, ValidateFunction } from "ajv";
import { schemaDir } from "./paths.js";

const require = createRequire(import.meta.url);
const Ajv2020 = require("ajv/dist/2020").default;
const addFormats = require("ajv-formats").default ?? require("ajv-formats");

export const SUPPORTED_SCHEMA_VERSION = "1.0";

const SCHEMAS = {
  manifest: "manifest.schema.json",
  navigation: "navigation.schema.json",
  page: "page.schema.json",
  sitemap: "sitemap.schema.json",
  images: "images.schema.json",
  report: "report.schema.json",
} as const;
type SchemaName = keyof typeof SCHEMAS;

let validators: Record<SchemaName, ValidateFunction> | null = null;

function getValidators(): Record<SchemaName, ValidateFunction> {
  if (validators) return validators;
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  const dir = schemaDir();
  const loaded = Object.fromEntries(
    Object.entries(SCHEMAS).map(([name, file]) => [name, JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"))]),
  ) as Record<SchemaName, { $id: string }>;
  for (const schema of Object.values(loaded)) ajv.addSchema(schema);
  validators = Object.fromEntries(
    Object.entries(loaded).map(([name, schema]) => [name, ajv.getSchema(schema.$id)!]),
  ) as Record<SchemaName, ValidateFunction>;
  return validators;
}

function describe(errors: ErrorObject[] | null | undefined): string[] {
  // if/then + oneOf produce noisy duplicates; keep the most specific messages
  const seen = new Set<string>();
  const out: string[] = [];
  for (const error of errors ?? []) {
    if (["if", "oneOf", "anyOf"].includes(error.keyword)) continue;
    const where = error.instancePath || "(root)";
    const extra = error.keyword === "additionalProperties" ? ` (${(error.params as { additionalProperty: string }).additionalProperty})` : "";
    const message = `${where}: ${error.message}${extra}`;
    if (!seen.has(message)) {
      seen.add(message);
      out.push(message);
    }
  }
  return out;
}

export type ManifestEntry = {
  path: string;
  title?: string | null;
  content: string;
  images?: string | null;
  markdown?: string | null;
  html?: string | null;
  aliases?: string[];
  dir?: string;
};
export type Manifest = { schemaVersion: string; sourceUrl: string; site?: { name?: string | null; lang?: string | null }; pages: ManifestEntry[] };

export type ArchiveValidation = { ok: boolean; errors: string[]; manifest?: Manifest };

export function readJson<T = unknown>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf8")) as T;
}

/** Validate an archive directory. Errors are human readable ("file: /json/pointer: message"). */
export function validateArchive(root: string, options: { resolveAsset?: (src: string) => string } = {}): ArchiveValidation {
  const resolveAsset = options.resolveAsset ?? ((src: string) => path.join(root, src));
  const errors: string[] = [];
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    return { ok: false, errors: [`${root}: archive directory not found`] };
  }
  const v = getValidators();

  const check = <T>(rel: string, schema: SchemaName, required = true): T | undefined => {
    const file = path.join(root, rel);
    if (!fs.existsSync(file)) {
      if (required) errors.push(`${rel}: file missing`);
      return undefined;
    }
    let data: unknown;
    try {
      data = readJson(file);
    } catch (error) {
      errors.push(`${rel}: invalid JSON (${(error as Error).message})`);
      return undefined;
    }
    const version = (data as { schemaVersion?: unknown })?.schemaVersion;
    if (typeof version !== "string" || version.split(".")[0] !== SUPPORTED_SCHEMA_VERSION.split(".")[0]) {
      errors.push(`${rel}: unsupported schemaVersion ${JSON.stringify(version)} – this generator supports ${SUPPORTED_SCHEMA_VERSION}`);
      return data as T;
    }
    if (!v[schema](data)) errors.push(...describe(v[schema].errors).map((e) => `${rel}: ${e}`));
    return data as T;
  };

  const manifest = check<Manifest>("manifest.json", "manifest");
  check("navigation.json", "navigation");
  check("sitemap.json", "sitemap", false);
  const registry = check<{ assets: { file: string }[] }>("assets/images.json", "images", false);
  if (!manifest || !Array.isArray(manifest.pages)) return { ok: false, errors, manifest };

  const seen = new Map<string, string>();
  for (const entry of manifest.pages) {
    const key = entry.path?.toLowerCase();
    if (seen.has(key)) errors.push(`manifest.json: page path ${entry.path} collides with ${seen.get(key)}`);
    seen.set(key, entry.path);
    const page = entry.content ? check<{ path: string }>(entry.content, "page") : undefined;
    if (page && page.path !== entry.path) errors.push(`${entry.content}: path ${page.path} does not match manifest path ${entry.path}`);
    if (entry.images) {
      const images = check<{ images: { src: string | null }[] }>(entry.images, "images", false);
      for (const image of images?.images ?? []) {
        if (image.src && !fs.existsSync(resolveAsset(image.src))) errors.push(`${entry.images}: image file missing ${image.src}`);
      }
    }
  }
  for (const asset of registry?.assets ?? []) {
    if (!fs.existsSync(resolveAsset(asset.file))) errors.push(`assets/images.json: file missing ${asset.file}`);
  }
  return { ok: errors.length === 0, errors, manifest };
}
