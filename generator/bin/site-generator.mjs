#!/usr/bin/env node
// Entry point when installed as a package: runs the TypeScript CLI through tsx.
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const tsx = require.resolve("tsx/cli");
const cli = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "cli.ts");
const result = spawnSync(process.execPath, [tsx, cli, ...process.argv.slice(2)], { stdio: "inherit" });
process.exit(result.status ?? 1);
