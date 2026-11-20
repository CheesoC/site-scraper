import sanitizeHtml from "sanitize-html";

const ALLOWED = {
  allowedTags: sanitizeHtml.defaults.allowedTags.concat(["img", "details", "summary", "figure", "figcaption", "del", "ins", "mark", "sub", "sup", "small"]),
  allowedAttributes: {
    a: ["href", "title"],
    img: ["src", "alt", "width", "height"],
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan", "scope"],
    abbr: ["title"],
    time: ["datetime"],
  },
  allowedSchemes: ["http", "https", "mailto", "tel"],
};

/**
 * Fallback for content that has no dedicated component:
 * - "html" blocks: sanitized HTML from the archive (sanitized again here, scripts never run)
 * - unknown block types (newer schema): their text content, so nothing disappears silently
 */
export default function FallbackBlock({ html, text, originalType }: { html?: string; text?: string; originalType?: string }) {
  if (html) {
    return <div className="fallback-block content-flow" data-fallback="html" dangerouslySetInnerHTML={{ __html: sanitizeHtml(html, ALLOWED) }} />;
  }
  return (
    <div className="fallback-block rounded-card border border-dashed border-line p-4 text-sm" data-fallback={originalType}>
      {text}
    </div>
  );
}

export function collectText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(collectText).filter(Boolean).join(" ");
  if (value && typeof value === "object") {
    return Object.entries(value)
      .filter(([key]) => !["type", "href", "src", "path", "url", "originalSrc"].includes(key))
      .map(([, v]) => collectText(v))
      .filter(Boolean)
      .join(" ");
  }
  return "";
}
