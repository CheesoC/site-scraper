import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkProject } from "../src/check";
import { GenerateError, generate } from "../src/generate";
import { ImportError, importContent, rewriteAssetPaths } from "../src/importer";
import { SAMPLE, copyArchive, readJson, tmpDir, writeJson } from "./helpers";

describe("rewriteAssetPaths", () => {
  it("rewrites archive asset references to public URLs, but never texts", () => {
    const input = { src: "assets/images/a.png", text: "assets/images/a.png", nested: [{ image: "assets/images/b.svg" }], other: "https://x/y.png" };
    expect(rewriteAssetPaths(input)).toEqual({ src: "/assets/images/a.png", text: "assets/images/a.png", nested: [{ image: "/assets/images/b.svg" }], other: "https://x/y.png" });
  });
});

describe("generate", () => {
  it("creates a project from the template with imported content and assets", () => {
    const out = path.join(tmpDir(), "site");
    const result = generate(SAMPLE, out);
    expect(result.check.errors).toEqual([]);
    expect(fs.existsSync(path.join(out, "app/[[...slug]]/page.tsx"))).toBe(true);
    expect(fs.existsSync(path.join(out, "content/pages/leistungen/seo/content.json"))).toBe(true);
    expect(fs.readdirSync(path.join(out, "public/assets/images"))).toHaveLength(6);
    const page = readJson(path.join(out, "content/pages/index/content.json"));
    expect(page.sections[0].blocks[2].src).toMatch(/^\/assets\/images\/.+-hero\.png$/);
    expect(readJson(path.join(out, "content/navigation.json")).logo.image).toMatch(/^\/assets\/images\//);
    expect(readJson(path.join(out, "package.json")).name).toBe("beispiel-agentur");
    expect(readJson(path.join(out, ".redesign-tool.json")).managed).toEqual(["content", "public/assets"]);
    expect(result.report.added).toHaveLength(7);
  });

  it("refuses to overwrite an existing project without --force", () => {
    const out = path.join(tmpDir(), "site");
    generate(SAMPLE, out);
    expect(() => generate(SAMPLE, out)).toThrow(GenerateError);
    expect(() => generate(SAMPLE, out, { force: true })).not.toThrow();
  });

  it("does not leave a half generated project behind for invalid archives", () => {
    const archive = copyArchive();
    fs.rmSync(path.join(archive, "navigation.json"));
    const out = path.join(tmpDir(), "site");
    expect(() => generate(archive, out)).toThrow(ImportError);
    expect(fs.existsSync(out)).toBe(false);
  });
});

describe("sync (re-import)", () => {
  it("updates content but keeps design changes and custom files", () => {
    const out = path.join(tmpDir(), "site");
    generate(SAMPLE, out);
    // redesign: change a component, the design tokens and add an own component
    const header = path.join(out, "components/layout/Header.tsx");
    fs.writeFileSync(header, fs.readFileSync(header, "utf8") + "\n// my redesign\n");
    const css = path.join(out, "app/globals.css");
    fs.writeFileSync(css, fs.readFileSync(css, "utf8").replace("#2563eb", "#e11d48"));
    fs.writeFileSync(path.join(out, "components/MyHero.tsx"), "export default function MyHero() { return null; }\n");

    // new crawl: one page changed, one removed, one added
    const archive = copyArchive();
    const manifest = readJson(path.join(archive, "manifest.json"));
    const seo = path.join(archive, "pages/leistungen/seo/content.json");
    const seoPage = readJson(seo);
    seoPage.sections[0].blocks[1].content[0].text = "Neuer Text.";
    writeJson(seo, seoPage);
    manifest.pages = manifest.pages.filter((p: { path: string }) => p.path !== "/impressum");
    fs.mkdirSync(path.join(archive, "pages/blog"), { recursive: true });
    writeJson(path.join(archive, "pages/blog/content.json"), { ...readJson(path.join(archive, "pages/impressum/content.json")), path: "/blog", title: "Blog" });
    manifest.pages.push({ path: "/blog", content: "pages/blog/content.json", dir: "pages/blog" });
    writeJson(path.join(archive, "manifest.json"), manifest);
    const nav = readJson(path.join(archive, "navigation.json"));
    nav.footer[1].children = nav.footer[1].children.filter((c: { path: string | null }) => c.path !== "/impressum");
    writeJson(path.join(archive, "navigation.json"), nav);

    const report = importContent(archive, out);
    expect(report.added).toEqual(["/blog"]);
    expect(report.removed).toEqual(["/impressum"]);
    expect(report.changed).toEqual(["/leistungen/seo"]);
    expect(report.unchanged).toBe(5);

    expect(fs.readFileSync(header, "utf8")).toContain("// my redesign");
    expect(fs.readFileSync(css, "utf8")).toContain("#e11d48");
    expect(fs.existsSync(path.join(out, "components/MyHero.tsx"))).toBe(true);
    expect(fs.existsSync(path.join(out, "content/pages/impressum"))).toBe(false);
    expect(readJson(path.join(out, "content/pages/leistungen/seo/content.json")).sections[0].blocks[1].content[0].text).toBe("Neuer Text.");
    expect(readJson(path.join(out, "content/import-report.json")).added).toEqual(["/blog"]);
    expect(checkProject(out).errors).toEqual([]);
  });

  it("keeps the old content when the new archive is invalid", () => {
    const out = path.join(tmpDir(), "site");
    generate(SAMPLE, out);
    const archive = copyArchive();
    fs.writeFileSync(path.join(archive, "manifest.json"), "{ broken");
    expect(() => importContent(archive, out)).toThrow(ImportError);
    expect(readJson(path.join(out, "content/manifest.json")).pages).toHaveLength(7);
  });
});
