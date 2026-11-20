import { getManifest, getNavigation } from "./content";
import type { NavItem } from "./schema";

export type { NavItem } from "./schema";

/** Main menu; falls back to the top-level pages of the manifest when no menu was extracted. */
export function getMainMenu(): NavItem[] {
  const navigation = getNavigation();
  if (navigation.main.length > 0) return navigation.main;
  return getManifest()
    .pages.filter((page) => page.path.split("/").length === 2)
    .map((page, order) => ({
      label: page.title || page.path,
      url: null,
      path: page.path,
      external: false,
      order,
      depth: 0,
      type: "main",
      children: [],
    }));
}

export function getFooterMenu(): NavItem[] {
  return getNavigation().footer;
}

export function getCallToActions(): NavItem[] {
  return getNavigation().cta ?? [];
}

export function getLogo() {
  return getNavigation().logo ?? null;
}

export function navHref(item: NavItem): string | null {
  if (item.path) return encodeURI(item.path).replace(/%23/g, "#");
  return item.url;
}
