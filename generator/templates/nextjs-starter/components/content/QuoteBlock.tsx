import type { Block, RichText as RichTextType } from "@/lib/schema";
import BlockRenderer from "./BlockRenderer";
import RichText from "./RichText";

export default function QuoteBlock({ blocks, cite }: { blocks: Block[]; cite?: RichTextType }) {
  return (
    <figure className="border-l-4 border-brand pl-5">
      <blockquote className="content-flow text-lg italic">
        {blocks.map((block, index) => (
          <BlockRenderer key={index} block={block} />
        ))}
      </blockquote>
      {cite && cite.length > 0 ? (
        <figcaption className="mt-2 text-sm text-muted">
          — <RichText nodes={cite} />
        </figcaption>
      ) : null}
    </figure>
  );
}
