import type { ReactNode } from "react";
import { assetUrl } from "@/lib/routes";
import type { Block, Section } from "@/lib/schema";
import BlockRenderer from "./BlockRenderer";
import CallToAction from "./CallToAction";
import CardGrid from "./CardGrid";
import ContentSection from "./ContentSection";

type CardBlock = Extract<Block, { type: "card" }>;

/** Renders blocks in their original order; consecutive cards are grouped into a responsive grid. */
export function renderBlocks(blocks: Block[]): ReactNode[] {
  const out: ReactNode[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    if (block.type === "card") {
      const cards: CardBlock[] = [];
      while (i < blocks.length && blocks[i].type === "card") {
        cards.push(blocks[i] as CardBlock);
        i++;
      }
      i--;
      out.push(<CardGrid key={`cards-${i}`} cards={cards} />);
      continue;
    }
    out.push(<BlockRenderer key={i} block={block} />);
  }
  return out;
}

/** The universal page renderer: every section of the archive, in order, with the shared section layout. */
export default function ContentRenderer({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections.map((section) => {
        let blocks = section.blocks;
        let background: string | null = null;
        const first = blocks[0];
        if (first?.type === "image" && first.role === "background" && section.type === "hero") {
          background = assetUrl(first.src);
          if (background) blocks = blocks.slice(1);
        }
        const rendered = renderBlocks(blocks);
        return (
          <ContentSection key={section.id} id={section.id} type={section.type} background={background}>
            {section.type === "cta" ? <CallToAction>{rendered}</CallToAction> : rendered}
          </ContentSection>
        );
      })}
    </>
  );
}
