import SmartLink from "@/components/SmartLink";
import { getSiteName } from "@/lib/content";
import { getCallToActions, getLogo, getMainMenu, navHref } from "@/lib/navigation";
import { assetUrl } from "@/lib/routes";
import MobileNavigation from "./MobileNavigation";
import Navigation from "./Navigation";

export default function Header() {
  const logo = getLogo();
  const items = getMainMenu();
  const ctas = getCallToActions();
  const siteName = getSiteName();
  const logoSrc = assetUrl(logo?.image);
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between gap-6">
        <SmartLink href={logo?.path ?? "/"} className="flex shrink-0 items-center gap-2 font-semibold">
          {logoSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoSrc} alt={logo?.alt || siteName} className="h-8 w-auto" />
          ) : (
            <span>{siteName}</span>
          )}
        </SmartLink>
        <Navigation items={items} />
        <div className="flex items-center gap-3">
          {ctas.map((cta) => {
            const href = navHref(cta);
            return href ? (
              <SmartLink key={`${cta.label}-${href}`} href={href} className="btn btn-primary hidden lg:inline-flex">
                {cta.label}
              </SmartLink>
            ) : null;
          })}
          <MobileNavigation items={items} ctas={ctas} />
        </div>
      </div>
    </header>
  );
}
