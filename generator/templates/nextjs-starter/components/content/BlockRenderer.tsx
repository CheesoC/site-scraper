import type { Block } from "@/lib/schema";
import Button from "./Button";
import Card from "./Card";
import CodeBlock from "./CodeBlock";
import EmbedBlock from "./EmbedBlock";
import FAQ from "./FAQ";
import FallbackBlock, { collectText } from "./FallbackBlock";
import FormBlock from "./FormBlock";
import Heading from "./Heading";
import ImageBlock from "./ImageBlock";
import ImageGallery from "./ImageGallery";
import ListBlock from "./ListBlock";
import Paragraph from "./Paragraph";
import QuoteBlock from "./QuoteBlock";
import TableBlock from "./TableBlock";

/** Maps one content block to its React component. */
export default function BlockRenderer({ block }: { block: Block }) {
  switch (block.type) {
    case "heading":
      return <Heading level={block.level} content={block.content} anchor={block.anchor} />;
    case "paragraph":
      return <Paragraph content={block.content} />;
    case "list":
      return <ListBlock ordered={block.ordered} items={block.items} />;
    case "table":
      return <TableBlock caption={block.caption} head={block.head} rows={block.rows} />;
    case "quote":
      return <QuoteBlock blocks={block.blocks} cite={block.cite} />;
    case "image":
      return <ImageBlock image={block} />;
    case "gallery":
      return <ImageGallery images={block.images} />;
    case "button":
      return <Button label={block.label} href={block.href} path={block.path} external={block.external} variant={block.variant} />;
    case "embed":
      return <EmbedBlock provider={block.provider} url={block.url} title={block.title} poster={block.poster} />;
    case "code":
      return <CodeBlock text={block.text} language={block.language} />;
    case "divider":
      return <hr className="border-line" />;
    case "card":
      return <Card blocks={block.blocks} link={block.link} />;
    case "accordion":
      return <FAQ items={block.items} />;
    case "form":
      return <FormBlock {...block} />;
    case "html":
      return <FallbackBlock html={block.html} />;
    default: {
      const unknown = block as { originalType?: string; data?: unknown };
      return <FallbackBlock originalType={unknown.originalType ?? "unknown"} text={collectText(unknown.data ?? block)} />;
    }
  }
}
