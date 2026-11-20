import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const REPO = path.resolve(import.meta.dirname, "..", "..");
export const SAMPLE = path.join(REPO, "examples", "sample-website-source");

export function tmpDir(prefix = "gen-"): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export function copyArchive(): string {
  const target = path.join(tmpDir("archive-"), "archive");
  fs.cpSync(SAMPLE, target, { recursive: true });
  return target;
}

export function readJson<T = any>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

export function writeJson(file: string, data: unknown) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}
