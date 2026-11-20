"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import SmartLink from "@/components/SmartLink";
import type { NavItem } from "@/lib/schema";
import { isActivePath } from "@/lib/routes";
import { itemHref } from "./Navigation";

function MobileItems({ items, current, depth = 0 }: { items: NavItem[]; current: string; depth?: number }) {
  return (
    <ul className={depth > 0 ? "ml-4 border-l border-line pl-3" : "space-y-1"}>
      {items.map((item) => {
        const href = itemHref(item);
        const link = href ? (
          <SmartLink
            href={href}
            aria-current={isActivePath(item.path, current, true) ? "page" : undefined}
            className="block rounded-md px-3 py-2 hover:bg-subtle aria-[current=page]:font-semibold aria-[current=page]:text-brand"
          >
            {item.label}
          </SmartLink>
        ) : (
          <span className="block px-3 py-2 font-medium">{item.label}</span>
        );
        if (item.children.length === 0) return <li key={`${item.order}-${item.label}`}>{link}</li>;
        return (
          <li key={`${item.order}-${item.label}`}>
            <details open={isActivePath(item.path, current)}>
              <summary className="flex cursor-pointer list-none items-center justify-between rounded-md pr-3 hover:bg-subtle">
                {link}
                <span aria-hidden="true">▾</span>
              </summary>
              <MobileItems items={item.children} current={current} depth={depth + 1} />
            </details>
          </li>
        );
      })}
    </ul>
  );
}

/** Mobile navigation: toggle button + panel with all levels. */
export default function MobileNavigation({ items, ctas }: { items: NavItem[]; ctas: NavItem[] }) {
  const current = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [current]);
  return (
    <div className="lg:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="mobile-navigation"
        onClick={() => setOpen((value) => !value)}
        className="rounded-md border border-line px-3 py-2 text-sm font-medium"
      >
        {open ? "Schließen" : "Menü"}
      </button>
      {open ? (
        <nav id="mobile-navigation" aria-label="Mobile Navigation" className="absolute inset-x-0 top-16 max-h-[calc(100vh-4rem)] overflow-y-auto border-b border-line bg-surface p-4 shadow-lg">
          <MobileItems items={items} current={current} />
          {ctas.length > 0 ? (
            <div className="mt-4 flex flex-col gap-2">
              {ctas.map((cta) => {
                const href = itemHref(cta);
                return href ? (
                  <SmartLink key={cta.label} href={href} className="btn btn-primary">
                    {cta.label}
                  </SmartLink>
                ) : null;
              })}
            </div>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
