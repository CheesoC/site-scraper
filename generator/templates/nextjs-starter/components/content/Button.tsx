import SmartLink from "@/components/SmartLink";
import { resolveHref } from "@/lib/routes";

type Props = { label: string; href: string; path?: string | null; external: boolean; variant?: "primary" | "secondary" | "link" };

export default function Button({ label, href, path, external, variant = "primary" }: Props) {
  const className = `btn btn-${variant}`;
  const target = resolveHref({ href, path, external });
  if (!target) {
    return (
      <span className={className} aria-disabled="true">
        {label}
      </span>
    );
  }
  return (
    <SmartLink href={target} className={className}>
      {label}
    </SmartLink>
  );
}
