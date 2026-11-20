/** Creates a new Next.js project from the starter template and imports the archive. */
import fs from "node:fs";
import path from "node:path";
import { checkProject, type CheckResult } from "./check.js";
import { importContent, type ImportReport } from "./importer.js";
import { TEMPLATE_DIR } from "./paths.js";

const SKIP = new Set(["node_modules", ".next", "out", "next-env.d.ts", "package-lock.json", ".content-import"]);

export class GenerateError extends Error {}

function copyTemplate(from: string, to: string) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    if (SKIP.has(entry.name) || entry.name.endsWith(".tsbuildinfo")) continue;
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) copyTemplate(src, dst);
    else fs.copyFileSync(src, dst);
  }
}

function packageName(siteName: string | null | undefined, fallback: string): string {
  const slug = (siteName || fallback)
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (slug || "generated-website").slice(0, 60);
}

export type GenerateResult = { project: string; report: ImportReport; check: CheckResult };

export function generate(source: string, output: string, options: { force?: boolean } = {}): GenerateResult {
  const project = path.resolve(output);
  if (fs.existsSync(project) && fs.readdirSync(project).length > 0) {
    if (!options.force) {
      throw new GenerateError(
        `Output ${project} already exists and is not empty. Use "npm run sync -- --source <archive> --project ${output}" to update its content, or --force to overwrite the whole project.`,
      );
    }
    fs.rmSync(project, { recursive: true, force: true });
  }
  copyTemplate(TEMPLATE_DIR, project);
  try {
    const report = importContent(source, project);
    const pkgFile = path.join(project, "package.json");
    const pkg = JSON.parse(fs.readFileSync(pkgFile, "utf8"));
    const manifest = JSON.parse(fs.readFileSync(path.join(project, "content", "manifest.json"), "utf8"));
    pkg.name = packageName(manifest.site?.name, path.basename(project));
    fs.writeFileSync(pkgFile, JSON.stringify(pkg, null, 2) + "\n");
    return { project, report, check: checkProject(project) };
  } catch (error) {
    fs.rmSync(project, { recursive: true, force: true });
    throw error;
  }
}
