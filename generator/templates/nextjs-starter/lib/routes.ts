/** URL path helpers shared by the content loader and the components. */

/** Normalize a request path or slug to the manifest form: "/", "/a/b" (decoded, no trailing slash). */
export function normalizePath(input: string | string[] | undefined | null): string {
  let path = Array.isArray(input) ? "/" + input.join("/") : input ?? "/";
  path = path.split("#")[0].split("?")[0];
  try {
    path = decodeURIComponent(path);
  } catch {
    // keep undecodable paths as they are
  }
  path = "/" + path.replace(/^\/+/, "").replace(/\/{2,}/g, "/");
  if (path.length > 1) path = path.replace(/\/+$/, "");
  return path || "/";
}

/** Slug segments for generateStaticParams: "/" -> [], "/a/b" -> ["a", "b"]. */
export function pathToSlug(path: string): string[] {
  return path === "/" ? [] : path.replace(/^\//, "").split("/");
}

export type LinkLike = { href: string; path?: string | null; external?: boolean };

/** Where a link should point in the generated site: local route for exported pages, original URL otherwise. */
export function resolveHref(link: LinkLike): string {
  if (link.path) return encodeURI(link.path).replace(/%23/g, "#");
  return link.href;
}

export function isExternal(link: LinkLike): boolean {
  return !link.path && /^https?:\/\//i.test(link.href);
}

/** true if `current` is `path` or one of its sub pages (used for the active navigation state). */
export function isActivePath(path: string | null | undefined, current: string, exact = false): boolean {
  if (!path) return false;
  const target = normalizePath(path);
  const here = normalizePath(current);
  if (target === "/" || exact) return target === here;
  return here === target || here.startsWith(target + "/");
}

/** Public URL of an imported asset ("/assets/images/..."). */
export function assetUrl(src: string | null | undefined): string | null {
  if (!src) return null;
  if (/^(https?:)?\/\//.test(src) || src.startsWith("/")) return src;
  return "/" + src.replace(/^\.?\//, "");
}
