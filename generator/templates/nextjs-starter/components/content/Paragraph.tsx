import type { RichText as RichTextType } from "@/lib/schema";
import RichText from "./RichText";

export default function Paragraph({ content }: { content: RichTextType }) {
  return (
    <p>
      <RichText nodes={content} />
    </p>
  );
}
