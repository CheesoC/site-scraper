import type { ReactNode } from "react";
import type { SectionType } from "@/lib/schema";

/** Layout wrapper per section type – the main hook for a redesign of page sections. */
const STYLES: Record<SectionType, string> = {
  hero: "bg-subtle py-16 sm:py-24",
  content: "py-10",
  cards: "py-12",
  faq: "py-12",
  testimonials: "bg-subtle py-12",
  gallery: "py-12",
  cta: "py-12",
  form: "py-12",
  generic: "py-8",
};

export default function ContentSection({ id, type, children, background }: { id: string; type: SectionType; children: ReactNode; background?: string | null }) {
  return (
    <section
      id={id}
      data-section-type={type}
      className={`relative ${STYLES[type]} ${background ? "bg-cover bg-center" : ""}`}
      style={background ? { backgroundImage: `linear-gradient(rgba(255,255,255,.85), rgba(255,255,255,.85)), url("${background}")` } : undefined}
    >
      <div className={`container-page content-flow ${type === "content" || type === "generic" || type === "faq" ? "max-w-3xl" : ""}`}>{children}</div>
    </section>
  );
}
