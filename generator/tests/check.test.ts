import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkProject, normalizeRoute } from "../src/check";
import { generate } from "../src/generate";
import { SAMPLE, readJson, tmpDir, writeJson } from "./helpers";

function project() {
  const out = path.join(tmpDir(), "site");
  generate(SAMPLE, out);
  return out;
}

describe("checkProject", () => {
  it("passes for a freshly generated project", () => {
    const result = checkProject(project());
    expect(result.ok).toBe(true);
    expect(result.stats.pages).toBe(7);
    expect(result.stats.fallbackBlocks).toBe(1);
  });

  it("finds broken internal links, missing images and unsupported blocks", () => {
    const out = project();
    const file = path.join(out, "content/pages/index/content.json");
    const page = readJson(file);
    page.sections[0].blocks.push({ type: "paragraph", content: [{ type: "link", href: "https://x/nirgends", path: "/nirgends", external: false, children: [{ type: "text", text: "x" }] }] });
    page.sections[0].blocks.push({ type: "timeline", entries: [] });
    writeJson(file, page);
    const image = fs.readdirSync(path.join(out, "public/assets/images")).find((f) => f.endsWith("hero.png"))!;
    fs.rmSync(path.join(out, "public/assets/images", image));
    const result = checkProject(out);
    const errors = result.errors.join("\n");
    expect(errors).toContain("internal link to /nirgends has no route");
    expect(errors).toContain(`image file missing public/assets/images/${image}`);
    expect(result.stats.unsupportedBlocks).toBe(1);
    expect(result.warnings.join("\n")).toContain('unsupported block type "timeline"');
  });

  it("detects route collisions and reserved paths", () => {
    const out = project();
    const file = path.join(out, "content/manifest.json");
    const manifest = readJson(file);
    manifest.pages.push({ ...manifest.pages[1], path: "/Leistungen" });
    manifest.pages.push({ ...manifest.pages[1], path: "/assets/x" });
    writeJson(file, manifest);
    const errors = checkProject(out).errors.join("\n");
    expect(errors).toContain("route collision: /Leistungen and /leistungen");
    expect(errors).toContain("route /assets/x collides with a reserved");
  });

  it("normalizes routes", () => {
    expect(normalizeRoute("/a/b/")).toBe("/a/b");
    expect(normalizeRoute("/%C3%BCber#x")).toBe("/über");
    expect(normalizeRoute("/")).toBe("/");
  });
});
