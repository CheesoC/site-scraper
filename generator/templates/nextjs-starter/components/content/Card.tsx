import SmartLink from "@/components/SmartLink";
import { resolveHref } from "@/lib/routes";
import type { Block, LinkTarget } from "@/lib/schema";
import BlockRenderer from "./BlockRenderer";

export default function Card({ blocks, link }: { blocks: Block[]; link?: LinkTarget | null }) {
  const body = (
    <div className="content-flow h-full rounded-card border border-line bg-surface p-6 shadow-sm transition hover:shadow-md">
      {blocks.map((block, index) => (
        <BlockRenderer key={index} block={block} />
      ))}
    </div>
  );
  if (!link) return body;
  return (
    <SmartLink href={resolveHref(link)} className="block h-full no-underline [&_a]:no-underline">
      {body}
    </SmartLink>
  );
}
