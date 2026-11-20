import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { validateArchive } from "../src/archive";
import { SAMPLE, copyArchive, readJson, writeJson } from "./helpers";

describe("validateArchive", () => {
  it("accepts the sample archive", () => {
    const result = validateArchive(SAMPLE);
    expect(result.errors).toEqual([]);
    expect(result.ok).toBe(true);
    expect(result.manifest?.pages).toHaveLength(7);
  });

  it("reports schema violations with file and JSON pointer", () => {
    const archive = copyArchive();
    const file = path.join(archive, "pages/kontakt/content.json");
    const page = readJson(file);
    page.sections[0].blocks[0].level = 9;
    delete page.title;
    writeJson(file, page);
    const result = validateArchive(archive);
    expect(result.ok).toBe(false);
    expect(result.errors).toContain("pages/kontakt/content.json: /sections/0/blocks/0/level: must be <= 6");
    expect(result.errors).toContain("pages/kontakt/content.json: (root): must have required property 'title'");
  });

  it("rejects other schema major versions", () => {
    const archive = copyArchive();
    const manifest = readJson(path.join(archive, "manifest.json"));
    manifest.schemaVersion = "2.0";
    writeJson(path.join(archive, "manifest.json"), manifest);
    const result = validateArchive(archive);
    expect(result.errors[0]).toMatch(/manifest.json: unsupported schemaVersion "2.0"/);
  });

  it("checks cross references (missing files, duplicate paths)", () => {
    const archive = copyArchive();
    const manifest = readJson(path.join(archive, "manifest.json"));
    manifest.pages.push({ ...manifest.pages[1], path: "/LEISTUNGEN" });
    writeJson(path.join(archive, "manifest.json"), manifest);
    fs.rmSync(path.join(archive, "pages/impressum/content.json"));
    const errors = validateArchive(archive).errors.join("\n");
    expect(errors).toContain("page path /LEISTUNGEN collides with /leistungen");
    expect(errors).toContain("pages/impressum/content.json: file missing");
  });

  it("fails clearly for a missing directory", () => {
    expect(validateArchive("/does/not/exist").errors[0]).toMatch(/archive directory not found/);
  });
});
