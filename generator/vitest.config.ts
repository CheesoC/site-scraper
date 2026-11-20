import path from "node:path";
import { defineConfig } from "vitest/config";

const template = path.resolve(import.meta.dirname, "templates/nextjs-starter");

export default defineConfig({
  resolve: {
    alias: { "@": template },
  },
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    testTimeout: 30000,
  },
});
