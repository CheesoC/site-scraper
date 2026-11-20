import type { ReactNode } from "react";

export default function CallToAction({ children }: { children: ReactNode }) {
  return <div className="content-flow rounded-card bg-brand p-8 text-brand-contrast sm:p-12 [&_.btn-primary]:bg-surface [&_.btn-primary]:text-ink [&_a:not(.btn)]:text-brand-contrast">{children}</div>;
}
