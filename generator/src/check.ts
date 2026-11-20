/** Post-import checks of a generated project (routes, files, links, images, collisions, unsupported blocks). */
import fs from "node:fs";
import path from "node:path";
import { readJson, validateArchive, type Manifest } from "./archive.js";

const KNOWN_BLOCKS = new Set([
  "heading", "paragraph", "list", "table", "quote", "image", "gallery", "button",
  "embed", "code", "divider", "card", "accordion", "form", "html",
]);
const RESERVED_PREFIXES = ["/_next", "/api", "/assets"];

export type CheckResult = {
  ok: boolean;
  errors: string[];
  warnings: string[];
  stats: { pages: number; links: number; images: number; fallbackBlocks: number; unsupportedBlocks: number };
};

export function normalizeRoute(p: string): string {
  let out = p.split("#")[0].split("?")[0];
  try {
    out = decodeURIComponent(out);
  } catch {
    /* keep */
  }
  out = "/" + out.replace(/^\/+/, "").replace(/\/+$/, "");
  return out;
}

export function checkProject(project: string): CheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const stats = { pages: 0, links: 0, images: 0, fallbackBlocks: 0, unsupportedBlocks: 0 };
  const content = path.join(project, "content");
  const manifestFile = path.join(content, "manifest.json");
  if (!fs.existsSync(manifestFile)) {
    return { ok: false, errors: ["content/manifest.json missing – run the import first"], warnings, stats };
  }
  // the imported content must still satisfy the schema (asset paths are public URLs now)
  const validation = validateArchive(content, { resolveAsset: (src) => path.join(project, "public", decodeURI(src)) });
  errors.push(...validation.errors.map((e) => `content/${e}`));

  const manifest = readJson<Manifest>(manifestFile);
  const routes = new Map<string, string>();
  for (const page of manifest.pages) {
    const route = normalizeRoute(page.path);
    const key = route.toLowerCase();
    if (routes.has(key)) errors.push(`route collision: ${page.path} and ${routes.get(key)}`);
    routes.set(key, page.path);
    if (RESERVED_PREFIXES.some((prefix) => route === prefix || route.startsWith(prefix + "/"))) {
      errors.push(`route ${page.path} collides with a reserved Next.js/public path`);
    }
    if (!fs.existsSync(path.join(content, page.content))) errors.push(`content file missing for ${page.path}: content/${page.content}`);
  }
  stats.pages = manifest.pages.length;
  const exists = (p: string) => routes.has(normalizeRoute(p).toLowerCase());

  const checkImage = (src: unknown, where: string) => {
    if (typeof src !== "string" || !src) return;
    stats.images++;
    if (src.startsWith("/assets/") && !fs.existsSync(path.join(project, "public", decodeURI(src)))) {
      errors.push(`${where}: image file missing public${src}`);
    }
  };

  /** Walk content; `isBlock` is true for elements of a "blocks" array. */
  const walk = (value: unknown, where: string, isBlock = false) => {
    if (Array.isArray(value)) {
      value.forEach((v) => walk(v, where, isBlock));
      return;
    }
    if (!value || typeof value !== "object") return;
    const node = value as Record<string, unknown>;
    if (isBlock && typeof node.type === "string") {
      if (node.type === "html") stats.fallbackBlocks++;
      if (!KNOWN_BLOCKS.has(node.type)) {
        stats.unsupportedBlocks++;
        warnings.push(`${where}: unsupported block type "${node.type}" (rendered by FallbackBlock)`);
      }
    }
    if (node.type === "image") checkImage(node.src, where);
    if (typeof node.path === "string" && ("href" in node || "url" in node)) {
      stats.links++;
      if (!exists(node.path)) errors.push(`${where}: internal link to ${node.path} has no route`);
    }
    for (const [key, child] of Object.entries(node)) walk(child, where, key === "blocks");
  };

  for (const page of manifest.pages) {
    const file = path.join(content, page.content);
    if (!fs.existsSync(file)) continue;
    const data = readJson<{ sections: unknown; breadcrumbs?: unknown; meta?: { og?: { image?: string | null } } }>(file);
    for (const section of (data.sections as { blocks: unknown }[]) ?? []) walk(section.blocks, `${page.path}`, true);
    walk(data.breadcrumbs ?? [], `${page.path} breadcrumbs`);
    checkImage(data.meta?.og?.image, `${page.path} og:image`);
  }

  const navFile = path.join(content, "navigation.json");
  if (fs.existsSync(navFile)) {
    const nav = readJson<{ main: unknown[]; footer: unknown[]; cta?: unknown[]; logo?: { image?: string | null; path?: string | null } | null }>(navFile);
    if (nav.main.length === 0) warnings.push("navigation.json: main menu is empty (the header falls back to top-level pages)");
    walk(nav.main, "navigation main");
    walk(nav.footer, "navigation footer");
    walk(nav.cta ?? [], "navigation cta");
    checkImage(nav.logo?.image, "navigation logo");
  } else {
    warnings.push("content/navigation.json missing");
  }
  if (!exists("/")) warnings.push("no home page (/) in the manifest");
  return { ok: errors.length === 0, errors, warnings, stats };
}
