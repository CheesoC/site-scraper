import SmartLink from "@/components/SmartLink";
import { navHref, type NavItem } from "@/lib/navigation";

export default function Breadcrumbs({ items }: { items: NavItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="container-page pt-6 text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => {
          const last = index === items.length - 1;
          const href = navHref(item);
          return (
            <li key={`${index}-${item.label}`} className="flex items-center gap-2">
              {href && !last ? <SmartLink href={href} className="hover:text-ink hover:underline">{item.label}</SmartLink> : <span aria-current={last ? "page" : undefined}>{item.label}</span>}
              {!last ? <span aria-hidden="true">/</span> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
