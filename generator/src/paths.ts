import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const GENERATOR_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const TEMPLATE_DIR = path.join(GENERATOR_ROOT, "templates", "nextjs-starter");

/** schemas/v1 of the repository (override with SITE_GENERATOR_SCHEMA_DIR). */
export function schemaDir(): string {
  if (process.env.SITE_GENERATOR_SCHEMA_DIR) return process.env.SITE_GENERATOR_SCHEMA_DIR;
  let dir = GENERATOR_ROOT;
  for (let i = 0; i < 5; i++) {
    const candidate = path.join(dir, "schemas", "v1");
    if (fs.existsSync(path.join(candidate, "page.schema.json"))) return candidate;
    dir = path.dirname(dir);
  }
  throw new Error("schemas/v1 not found – set SITE_GENERATOR_SCHEMA_DIR");
}
