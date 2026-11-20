import type { ListItem } from "@/lib/schema";
import BlockRenderer from "./BlockRenderer";
import RichText from "./RichText";

export default function ListBlock({ ordered, items }: { ordered: boolean; items: ListItem[] }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag>
      {items.map((item, index) => (
        <li key={index}>
          <RichText nodes={item.content} />
          {item.blocks?.map((block, i) => <BlockRenderer key={i} block={block} />)}
        </li>
      ))}
    </Tag>
  );
}
