import type { RichText as RichTextType } from "@/lib/schema";
import RichText from "./RichText";

export default function Heading({ level, content, anchor }: { level: number; content: RichTextType; anchor?: string | null }) {
  const Tag = `h${Math.min(Math.max(level, 1), 6)}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
  return (
    <Tag id={anchor ?? undefined}>
      <RichText nodes={content} />
    </Tag>
  );
}
