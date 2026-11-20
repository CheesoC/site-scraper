import type { Block, RichText as RichTextType } from "@/lib/schema";
import BlockRenderer from "./BlockRenderer";
import RichText from "./RichText";

/** Accordions, FAQs and description lists – native <details> works without JavaScript. */
export default function FAQ({ items }: { items: { title: RichTextType; blocks: Block[] }[] }) {
  return (
    <div className="divide-y divide-line rounded-card border border-line">
      {items.map((item, index) => (
        <details key={index} className="group p-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
            <span>
              <RichText nodes={item.title} />
            </span>
            <span aria-hidden="true" className="transition group-open:rotate-180">
              ▾
            </span>
          </summary>
          <div className="content-flow mt-3 text-muted">
            {item.blocks.map((block, i) => (
              <BlockRenderer key={i} block={block} />
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}
