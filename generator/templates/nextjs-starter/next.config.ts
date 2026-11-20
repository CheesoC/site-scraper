import fs from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

/** Redirects from original URL variants (manifest "aliases") to the local routes. */
function aliasRedirects() {
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(process.cwd(), "content", "manifest.json"), "utf8"));
    const redirects: { source: string; destination: string; permanent: boolean }[] = [];
    for (const page of manifest.pages ?? []) {
      for (const alias of page.aliases ?? []) {
        if (alias !== page.path && /^\/[^?#:*()]*$/.test(alias)) {
          redirects.push({ source: encodeURI(alias), destination: encodeURI(page.path), permanent: true });
        }
      }
    }
    return redirects;
  } catch {
    return [];
  }
}

const nextConfig: NextConfig = {
  images: { unoptimized: true },
  async redirects() {
    return aliasRedirects();
  },
};

export default nextConfig;
