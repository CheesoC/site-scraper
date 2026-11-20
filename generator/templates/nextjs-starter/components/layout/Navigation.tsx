"use client";

import { usePathname } from "next/navigation";
import SmartLink from "@/components/SmartLink";
import type { NavItem } from "@/lib/schema";
import { isActivePath } from "@/lib/routes";

export function itemHref(item: NavItem): string | null {
  if (item.path) return encodeURI(item.path).replace(/%23/g, "#");
  return item.url;
}

function SubItems({ items, current }: { items: NavItem[]; current: string }) {
  return (
    <ul className="space-y-1">
      {items.map((child) => {
        const href = itemHref(child);
        return (
          <li key={`${child.order}-${child.label}`}>
            {href ? (
              <SmartLink
                href={href}
                aria-current={isActivePath(child.path, current, true) ? "page" : undefined}
                className="block rounded-md px-3 py-2 text-sm hover:bg-subtle aria-[current=page]:font-semibold aria-[current=page]:text-brand"
              >
                {child.label}
              </SmartLink>
            ) : (
              <span className="block px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-muted">{child.label}</span>
            )}
            {child.children.length > 0 ? (
              <div className="pl-3">
                <SubItems items={child.children} current={current} />
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** Desktop navigation: original order, nested dropdowns (hover and keyboard focus), active state. */
export default function Navigation({ items }: { items: NavItem[] }) {
  const current = usePathname() ?? "/";
  return (
    <nav aria-label="Hauptnavigation" className="hidden flex-1 lg:block">
      <ul className="flex items-center gap-1">
        {items.map((item) => {
          const href = itemHref(item);
          const active = isActivePath(item.path, current);
          const hasChildren = item.children.length > 0;
          return (
            <li key={`${item.order}-${item.label}`} className="group relative">
              {href ? (
                <SmartLink
                  href={href}
                  aria-current={isActivePath(item.path, current, true) ? "page" : undefined}
                  aria-haspopup={hasChildren ? "true" : undefined}
                  className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium hover:bg-subtle ${active ? "text-brand" : ""}`}
                >
                  {item.label}
                  {hasChildren ? <span aria-hidden="true">▾</span> : null}
                </SmartLink>
              ) : (
                <button type="button" aria-haspopup="true" className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium hover:bg-subtle">
                  {item.label}
                  {hasChildren ? <span aria-hidden="true">▾</span> : null}
                </button>
              )}
              {hasChildren ? (
                <div className="invisible absolute left-0 top-full z-50 min-w-60 pt-2 opacity-0 transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                  <div className="rounded-card border border-line bg-surface p-2 shadow-lg">
                    <SubItems items={item.children} current={current} />
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
