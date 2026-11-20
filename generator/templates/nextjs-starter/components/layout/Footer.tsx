import SmartLink from "@/components/SmartLink";
import { getSiteName } from "@/lib/content";
import { getFooterMenu, navHref, type NavItem } from "@/lib/navigation";

function FooterLink({ item }: { item: NavItem }) {
  const href = navHref(item);
  if (!href) return <span>{item.label}</span>;
  return (
    <SmartLink href={href} className="hover:text-ink hover:underline">
      {item.label}
    </SmartLink>
  );
}

/** Footer from navigation.json: groups become columns, single links a link row. */
export default function Footer() {
  const items = getFooterMenu();
  const groups = items.filter((item) => item.children.length > 0);
  const singles = items.filter((item) => item.children.length === 0);
  const year = new Date().getFullYear();
  return (
    <footer className="mt-16 border-t border-line bg-subtle">
      <div className="container-page py-12 text-sm text-muted">
        {groups.length > 0 ? (
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {groups.map((group) => (
              <div key={`${group.order}-${group.label}`}>
                <p className="mb-3 font-semibold text-ink">{navHref(group) ? <FooterLink item={group} /> : group.label}</p>
                <ul className="space-y-2">
                  {group.children.map((child) => (
                    <li key={`${child.order}-${child.label}`}>
                      <FooterLink item={child} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : null}
        {singles.length > 0 ? (
          <ul className={`flex flex-wrap gap-x-6 gap-y-2 ${groups.length > 0 ? "mt-10" : ""}`}>
            {singles.map((item) => (
              <li key={`${item.order}-${item.label}`}>
                <FooterLink item={item} />
              </li>
            ))}
          </ul>
        ) : null}
        <p className="mt-10 text-xs">
          © {year} {getSiteName()}
        </p>
      </div>
    </footer>
  );
}
