/**
 * End-to-end smoke test: archive -> generated project -> npm install -> next build -> next start -> Playwright.
 *
 *   npm run test:e2e                                   # uses examples/sample-website-source
 *   npm run test:e2e -- --source ../outputs/x-source   # any archive (e.g. a real scraper run)
 *
 * Needs Playwright with Chromium (npx playwright install chromium).
 */
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { generate } from "../../src/generate";

const ROOT = path.resolve(import.meta.dirname, "..", "..", "..");
const { values } = parseArgs({
  options: {
    source: { type: "string", default: path.join(ROOT, "examples", "sample-website-source") },
    output: { type: "string", default: path.join(ROOT, "outputs", "e2e-website") },
    "skip-install": { type: "boolean", default: false },
  },
});

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require("playwright");
  } catch {
    const globalRoot = spawnSync("npm", ["root", "-g"], { encoding: "utf8" }).stdout.trim();
    return createRequire(path.join(globalRoot, "noop.js"))("playwright");
  }
}

function run(cmd: string, args: string[], cwd: string) {
  console.log(`$ ${cmd} ${args.join(" ")}`);
  const result = spawnSync(cmd, args, { cwd, stdio: "inherit", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" } });
  if (result.status !== 0) throw new Error(`${cmd} ${args.join(" ")} failed with ${result.status}`);
}

function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, () => {
      const port = (server.address() as net.AddressInfo).port;
      server.close(() => resolve(port));
    });
  });
}

async function waitFor(url: string, timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.status < 500) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`server at ${url} did not start`);
}

const failures: string[] = [];
function expect(condition: unknown, message: string) {
  if (condition) console.log(`  ✓ ${message}`);
  else {
    console.log(`  ✖ ${message}`);
    failures.push(message);
  }
}

async function main() {
  const source = path.resolve(values.source!);
  const output = path.resolve(values.output!);
  const nodeModules = path.join(output, "node_modules");
  const keep = fs.existsSync(nodeModules) ? fs.mkdtempSync(path.join(path.dirname(output), ".nm-")) : null;
  if (keep) fs.renameSync(nodeModules, path.join(keep, "node_modules")); // reuse a previous install
  console.log(`Generating ${output} from ${source}`);
  const result = generate(source, output, { force: true });
  if (keep) {
    fs.renameSync(path.join(keep, "node_modules"), nodeModules);
    fs.rmSync(keep, { recursive: true, force: true });
  }
  expect(result.check.ok, `post-import check passes (${result.check.errors.length} errors)`);
  for (const error of result.check.errors.slice(0, 10)) console.log(`      ${error}`);

  if (!values["skip-install"] || !fs.existsSync(nodeModules)) run("npm", ["install", "--no-audit", "--no-fund", "--loglevel=error"], output);
  run("npm", ["run", "build"], output);

  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const server = spawn("npx", ["next", "start", "-p", String(port)], { cwd: output, stdio: "ignore", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" }, detached: true });
  try {
    await waitFor(base + "/");
    const manifest = JSON.parse(fs.readFileSync(path.join(output, "content", "manifest.json"), "utf8"));
    const navigation = JSON.parse(fs.readFileSync(path.join(output, "content", "navigation.json"), "utf8"));
    const { chromium } = loadPlaywright();
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const consoleErrors: string[] = [];
    page.on("console", (msg: { type(): string; text(): string }) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    console.log("Routes:");
    for (const entry of manifest.pages) {
      const url = base + encodeURI(entry.path);
      const response = await page.goto(url, { waitUntil: "load" });
      const content = JSON.parse(fs.readFileSync(path.join(output, "content", entry.content), "utf8"));
      const h1 = content.meta?.h1;
      const text = await page.locator("main").innerText();
      const broken = await page.$$eval("main img", (imgs: HTMLImageElement[]) => imgs.filter((img) => img.complete && img.naturalWidth === 0).map((img) => img.src));
      expect(response?.status() === 200 && (!h1 || text.replace(/\s+/g, " ").includes(h1.replace(/\s+/g, " ").trim())) && broken.length === 0, `${entry.path} → 200, content rendered, ${broken.length} broken images`);
    }

    console.log("Navigation:");
    await page.goto(base + "/", { waitUntil: "load" });
    const withChildren = navigation.main.find((item: { children: unknown[]; path: string | null }) => item.children.length > 0);
    const target = withChildren?.children.find((c: { path: string | null }) => c.path);
    if (withChildren && target) {
      await page.locator('nav[aria-label="Hauptnavigation"] > ul > li').filter({ hasText: withChildren.label }).first().hover();
      await page.locator('nav[aria-label="Hauptnavigation"]').getByRole("link", { name: target.label, exact: true }).first().click();
      await page.waitForURL((url: URL) => decodeURI(url.pathname) === target.path.split("#")[0], { timeout: 10000 }).catch(() => undefined);
      expect(decodeURI(new URL(page.url()).pathname) === target.path.split("#")[0], `dropdown link "${withChildren.label} → ${target.label}" navigates to ${target.path}`);
    } else {
      expect(navigation.main.length > 0 || manifest.pages.length > 0, "main navigation present");
    }
    const firstFooter = navigation.footer.flatMap((i: { children: unknown[] }) => [i, ...(i.children as unknown[])]).find((i: { path: string | null }) => i.path);
    if (firstFooter) {
      await page.goto(base + "/", { waitUntil: "load" });
      expect(await page.locator("footer").getByRole("link", { name: firstFooter.label }).count() > 0, `footer link "${firstFooter.label}" present`);
    }

    console.log("Mobile:");
    const mobile = await browser.newPage({ viewport: { width: 390, height: 800 } });
    await mobile.goto(base + "/", { waitUntil: "load" });
    await mobile.click('button[aria-controls="mobile-navigation"]');
    expect(await mobile.locator("#mobile-navigation").isVisible(), "mobile navigation opens");

    console.log("Errors:");
    const notFound = await page.goto(base + "/diese-seite-gibt-es-nicht", { waitUntil: "load" });
    expect(notFound?.status() === 404, "unknown route returns 404");
    const alias = manifest.pages.flatMap((p: { aliases?: string[]; path: string }) => (p.aliases ?? []).map((a) => [a, p.path]))[0];
    if (alias) {
      await page.goto(base + encodeURI(alias[0]), { waitUntil: "load" });
      expect(decodeURI(new URL(page.url()).pathname) === alias[1], `alias ${alias[0]} redirects to ${alias[1]}`);
    }
    expect(consoleErrors.filter((e) => !e.includes("404")).length === 0, `no console errors (${consoleErrors.join(" | ").slice(0, 300)})`);
    await browser.close();
  } finally {
    try {
      process.kill(-server.pid!, "SIGTERM");
    } catch {
      /* already stopped */
    }
  }
  if (failures.length) {
    console.log(`\n${failures.length} check(s) failed`);
    process.exit(1);
  }
  console.log("\nE2E OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
