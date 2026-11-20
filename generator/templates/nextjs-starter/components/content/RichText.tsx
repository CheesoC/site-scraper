import { Fragment, type ReactNode } from "react";
import SmartLink from "@/components/SmartLink";
import { resolveHref } from "@/lib/routes";
import type { InlineNode } from "@/lib/schema";

const MARK_TAGS = {
  bold: "strong",
  italic: "em",
  underline: "u",
  strike: "s",
  code: "code",
  sub: "sub",
  sup: "sup",
  mark: "mark",
} as const;

function renderNode(node: InlineNode, key: number): ReactNode {
  if (node.type === "break") return <br key={key} />;
  if (node.type === "link") {
    return (
      <SmartLink key={key} href={resolveHref(node)} title={node.title ?? undefined}>
        <RichText nodes={node.children} />
      </SmartLink>
    );
  }
  let content: ReactNode = node.text;
  for (const mark of node.marks ?? []) {
    const Tag = MARK_TAGS[mark];
    content = <Tag>{content}</Tag>;
  }
  return <Fragment key={key}>{content}</Fragment>;
}

/** Inline content (text with marks, links, line breaks) exactly as extracted. */
export default function RichText({ nodes }: { nodes: InlineNode[] | undefined }) {
  if (!nodes || nodes.length === 0) return null;
  return <>{nodes.map(renderNode)}</>;
}

export function plainText(nodes: InlineNode[] | undefined): string {
  return (nodes ?? [])
    .map((node) => (node.type === "text" ? node.text : node.type === "link" ? plainText(node.children) : "\n"))
    .join("");
}
