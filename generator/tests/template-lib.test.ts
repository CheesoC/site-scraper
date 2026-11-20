import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { generate } from "../src/generate";
import { SAMPLE, tmpDir } from "./helpers";
import { assetUrl, isActivePath, normalizePath, pathToSlug, resolveHref } from "@/lib/routes";
import { blockSchema, pageSchema } from "@/lib/schema";

describe("template lib/routes", () => {
  it("normalizes slugs and paths", () => {
    expect(normalizePath(undefined)).toBe("/");
    expect(normalizePath([])).toBe("/");
    expect(normalizePath(["leistungen", "seo"])).toBe("/leistungen/seo");
    expect(normalizePath(["%C3%BCber-uns"])).toBe("/über-uns");
    expect(normalizePath("/a//b/?x=1#y")).toBe("/a/b");
    expect(pathToSlug("/")).toEqual([]);
    expect(pathToSlug("/a/b")).toEqual(["a", "b"]);
  });

  it("resolves links to local routes or original URLs", () => {
    expect(resolveHref({ href: "https://ex.com/a", path: "/a#x", external: false })).toBe("/a#x");
    expect(resolveHref({ href: "https://ex.com/über", path: "/über", external: false })).toBe("/%C3%BCber");
    expect(resolveHref({ href: "https://other.com/", path: null, external: true })).toBe("https://other.com/");
    expect(resolveHref({ href: "mailto:a@b.de", external: true })).toBe("mailto:a@b.de");
  });

  it("computes the active navigation state", () => {
    expect(isActivePath("/leistungen", "/leistungen/seo")).toBe(true);
    expect(isActivePath("/leistungen", "/leistungen/seo", true)).toBe(false);
    expect(isActivePath("/", "/kontakt")).toBe(false);
    expect(isActivePath("/", "/")).toBe(true);
    expect(isActivePath(null, "/")).toBe(false);
  });

  it("maps asset paths", () => {
    expect(assetUrl("assets/images/a.png")).toBe("/assets/images/a.png");
    expect(assetUrl("/assets/images/a.png")).toBe("/assets/images/a.png");
    expect(assetUrl(null)).toBeNull();
  });
});

describe("template lib/schema", () => {
  it("keeps unknown block types instead of dropping them", () => {
    const parsed = blockSchema.parse({ type: "timeline", entries: [{ text: "2020" }] });
    expect(parsed).toEqual({ type: "unknown", originalType: "timeline", data: { type: "timeline", entries: [{ text: "2020" }] } });
  });

  it("rejects invalid known blocks", () => {
    expect(blockSchema.safeParse({ type: "heading", level: 7, content: [] }).success).toBe(false);
  });

  it("maps unknown section types to generic", () => {
    const page = pageSchema.parse({ schemaVersion: "1.3", path: "/", url: "https://x/", title: "x", meta: {}, sections: [{ id: "s", type: "pricing", blocks: [] }] });
    expect(page.sections[0].type).toBe("generic");
  });

  it("rejects other schema major versions", () => {
    expect(pageSchema.safeParse({ schemaVersion: "2.0", path: "/", url: "", title: "", meta: {}, sections: [] }).success).toBe(false);
  });
});

describe("template lib/content (loader)", () => {
  let content: typeof import("@/lib/content");
  let navigation: typeof import("@/lib/navigation");

  beforeAll(async () => {
    const out = path.join(tmpDir(), "site");
    generate(SAMPLE, out);
    process.env.CONTENT_DIR = path.join(out, "content");
    content = await import("@/lib/content");
    navigation = await import("@/lib/navigation");
  });

  it("lists all routes and resolves pages by slug", () => {
    expect(content.getAllPaths()).toEqual(["/", "/leistungen", "/leistungen/webdesign", "/leistungen/seo", "/ueber-uns", "/kontakt", "/impressum"]);
    expect(content.getPage("/leistungen/seo")?.title).toBe("SEO");
    expect(content.findPage(["leistungen", "seo"])?.path).toBe("/leistungen/seo");
    expect(content.getPage("/nicht-da")).toBeUndefined();
  });

  it("provides site data and navigation", () => {
    expect(content.getSiteName()).toBe("Beispiel Agentur");
    expect(content.getSiteLang()).toBe("de");
    const main = navigation.getMainMenu();
    expect(main.map((i) => i.label)).toEqual(["Start", "Leistungen", "Über uns", "Kontakt"]);
    expect(main[1].children.map((i) => i.path)).toEqual(["/leistungen/webdesign", "/leistungen/seo"]);
    expect(navigation.getLogo()?.image).toMatch(/^\/assets\/images\//);
    expect(navigation.navHref(navigation.getFooterMenu()[1].children[1])).toBe("https://www.linkedin.com/");
  });
});
