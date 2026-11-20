/**
 * site-generator CLI
 *
 *   npm run generate -- --source ./outputs/example-source --output ./outputs/example-website [--force]
 *   npm run sync     -- --source ./outputs/example-source --project ./outputs/example-website
 *   npm run validate -- --source ./outputs/example-source
 *   npm run check    -- --project ./outputs/example-website
 */
import path from "node:path";
import { parseArgs } from "node:util";
import { validateArchive } from "./archive.js";
import { checkProject, type CheckResult } from "./check.js";
import { GenerateError, generate } from "./generate.js";
import { ImportError, importContent, type ImportReport } from "./importer.js";

const USAGE = `Usage:
  site-generator generate --source <archive> --output <project> [--force]
  site-generator sync     --source <archive> --project <project>
  site-generator validate --source <archive>
  site-generator check    --project <project>`;

function printCheck(result: CheckResult) {
  const { stats } = result;
  console.log(`  Prüfung: ${stats.pages} Seiten, ${stats.links} interne Links, ${stats.images} Bilder, ${stats.fallbackBlocks} HTML-Fallbacks, ${stats.unsupportedBlocks} unbekannte Blöcke`);
  for (const warning of result.warnings.slice(0, 20)) console.log(`  ⚠ ${warning}`);
  for (const error of result.errors.slice(0, 50)) console.log(`  ✖ ${error}`);
  if (result.errors.length > 50) console.log(`  … ${result.errors.length - 50} weitere Fehler`);
}

function printReport(report: ImportReport) {
  console.log(`  Import: ${report.pages} Seiten, ${report.assets} Bilder (neu: ${report.added.length}, geändert: ${report.changed.length}, entfernt: ${report.removed.length}, unverändert: ${report.unchanged})`);
  for (const p of report.added.slice(0, 20)) console.log(`    + ${p}`);
  for (const p of report.changed.slice(0, 20)) console.log(`    ~ ${p}`);
  for (const p of report.removed.slice(0, 20)) console.log(`    - ${p}`);
}

export function main(argv: string[]): number {
  const [command, ...rest] = argv;
  const { values } = parseArgs({
    args: rest,
    options: {
      source: { type: "string" },
      output: { type: "string" },
      project: { type: "string" },
      force: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (!command || values.help) {
    console.log(USAGE);
    return command ? 0 : 1;
  }
  try {
    switch (command) {
      case "validate": {
        if (!values.source) throw new GenerateError("--source is required");
        const result = validateArchive(path.resolve(values.source));
        if (result.ok) {
          console.log(`OK: ${values.source} entspricht Content Schema v1.0 (${result.manifest?.pages.length} Seiten)`);
          return 0;
        }
        console.log(`${result.errors.length} Problem(e) in ${values.source}:`);
        for (const error of result.errors.slice(0, 200)) console.log(`  - ${error}`);
        return 1;
      }
      case "generate": {
        if (!values.source || !values.output) throw new GenerateError("--source and --output are required");
        const result = generate(values.source, values.output, { force: values.force });
        console.log(`Website erzeugt: ${result.project}`);
        printReport(result.report);
        printCheck(result.check);
        console.log(`\nStarten:\n  cd ${path.relative(process.cwd(), result.project) || "."}\n  npm install\n  npm run dev`);
        return result.check.ok ? 0 : 2;
      }
      case "sync": {
        if (!values.source || !values.project) throw new GenerateError("--source and --project are required");
        const report = importContent(values.source, values.project);
        console.log(`Inhalte synchronisiert: ${path.resolve(values.project)} (nur content/ und public/assets/ ersetzt)`);
        printReport(report);
        const check = checkProject(path.resolve(values.project));
        printCheck(check);
        return check.ok ? 0 : 2;
      }
      case "check": {
        if (!values.project) throw new GenerateError("--project is required");
        const check = checkProject(path.resolve(values.project));
        printCheck(check);
        console.log(check.ok ? "OK" : "Fehler gefunden");
        return check.ok ? 0 : 1;
      }
      default:
        console.log(`Unknown command "${command}"\n${USAGE}`);
        return 1;
    }
  } catch (error) {
    if (error instanceof ImportError) {
      console.error(`✖ ${error.message}`);
      for (const detail of error.details.slice(0, 50)) console.error(`  - ${detail}`);
      return 1;
    }
    if (error instanceof GenerateError) {
      console.error(`✖ ${error.message}`);
      return 1;
    }
    throw error;
  }
}

const isEntry = process.argv[1] && /cli\.(ts|js|mjs)$/.test(process.argv[1]);
if (isEntry) process.exit(main(process.argv.slice(2)));
