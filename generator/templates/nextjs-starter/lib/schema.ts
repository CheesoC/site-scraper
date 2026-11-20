/**
 * Zod models of Content Schema v1.0 (see schemas/v1 in the site-scraper repository).
 * They validate the imported content at runtime and provide the TypeScript types.
 */
import { z } from "zod";

export const SUPPORTED_SCHEMA_MAJOR = "1";

const schemaVersion = z.string().refine((v) => v.split(".")[0] === SUPPORTED_SCHEMA_MAJOR, {
  message: `unsupported schemaVersion (expected ${SUPPORTED_SCHEMA_MAJOR}.x)`,
});
const nullableString = z.string().nullable().optional();

export const markSchema = z.enum(["bold", "italic", "underline", "strike", "code", "sub", "sup", "mark"]);

export type InlineNode =
  | { type: "text"; text: string; marks?: z.infer<typeof markSchema>[] }
  | { type: "link"; href: string; path?: string | null; external: boolean; title?: string | null; children: InlineNode[] }
  | { type: "break" };

export const inlineSchema: z.ZodType<InlineNode> = z.lazy(() =>
  z.discriminatedUnion("type", [
    z.object({ type: z.literal("text"), text: z.string(), marks: z.array(markSchema).optional() }),
    z.object({
      type: z.literal("link"),
      href: z.string(),
      path: z.string().nullable().optional(),
      external: z.boolean(),
      title: nullableString,
      children: z.array(inlineSchema),
    }),
    z.object({ type: z.literal("break") }),
  ]),
);
export const richTextSchema = z.array(inlineSchema);
export type RichText = InlineNode[];

export const linkTargetSchema = z.object({
  href: z.string(),
  path: z.string().nullable().optional(),
  external: z.boolean(),
});
export type LinkTarget = z.infer<typeof linkTargetSchema>;

export const imageSchema = z.object({
  type: z.literal("image"),
  src: z.string().nullable(),
  originalSrc: z.string(),
  alt: z.string(),
  caption: richTextSchema.optional(),
  width: z.number().int().nullable().optional(),
  height: z.number().int().nullable().optional(),
  link: linkTargetSchema.nullable().optional(),
  role: z.enum(["content", "background", "logo", "icon"]).optional(),
});
export type ImageBlock = z.infer<typeof imageSchema>;

export type TableCell = { content: RichText; header?: boolean; colspan?: number; rowspan?: number };
export type ListItem = { content: RichText; blocks?: Block[] };

export type Block =
  | { type: "heading"; level: number; content: RichText; anchor?: string | null }
  | { type: "paragraph"; content: RichText }
  | { type: "list"; ordered: boolean; items: ListItem[] }
  | { type: "table"; caption?: RichText; head?: TableCell[][]; rows: TableCell[][] }
  | { type: "quote"; blocks: Block[]; cite?: RichText }
  | ImageBlock
  | { type: "gallery"; images: ImageBlock[] }
  | { type: "button"; label: string; href: string; path?: string | null; external: boolean; variant?: "primary" | "secondary" | "link" }
  | {
      type: "embed";
      provider: "youtube" | "vimeo" | "video" | "audio" | "map" | "iframe";
      url: string;
      title?: string | null;
      poster?: string | null;
      width?: number | null;
      height?: number | null;
    }
  | { type: "code"; text: string; language?: string | null }
  | { type: "divider" }
  | { type: "card"; blocks: Block[]; link?: LinkTarget | null }
  | { type: "accordion"; items: { title: RichText; blocks: Block[] }[] }
  | {
      type: "form";
      action?: string | null;
      method?: string | null;
      submitLabel?: string | null;
      fields: {
        name: string;
        label?: string | null;
        inputType: string;
        required?: boolean;
        placeholder?: string | null;
        options?: string[];
      }[];
    }
  | { type: "html"; html: string; text?: string; reason?: string | null }
  /** Block types of a newer schema minor version: rendered by the FallbackBlock. */
  | { type: "unknown"; originalType: string; data: Record<string, unknown> };

const cellSchema = z.object({
  content: richTextSchema,
  header: z.boolean().optional(),
  colspan: z.number().int().optional(),
  rowspan: z.number().int().optional(),
});

const knownBlockSchema: z.ZodType<Block> = z.lazy(() =>
  z.discriminatedUnion("type", [
    z.object({ type: z.literal("heading"), level: z.number().int().min(1).max(6), content: richTextSchema, anchor: nullableString }),
    z.object({ type: z.literal("paragraph"), content: richTextSchema }),
    z.object({
      type: z.literal("list"),
      ordered: z.boolean(),
      items: z.array(z.object({ content: richTextSchema, blocks: z.array(blockSchema).optional() })),
    }),
    z.object({
      type: z.literal("table"),
      caption: richTextSchema.optional(),
      head: z.array(z.array(cellSchema)).optional(),
      rows: z.array(z.array(cellSchema)),
    }),
    z.object({ type: z.literal("quote"), blocks: z.array(blockSchema), cite: richTextSchema.optional() }),
    imageSchema,
    z.object({ type: z.literal("gallery"), images: z.array(imageSchema) }),
    z.object({
      type: z.literal("button"),
      label: z.string(),
      href: z.string(),
      path: z.string().nullable().optional(),
      external: z.boolean(),
      variant: z.enum(["primary", "secondary", "link"]).optional(),
    }),
    z.object({
      type: z.literal("embed"),
      provider: z.enum(["youtube", "vimeo", "video", "audio", "map", "iframe"]),
      url: z.string(),
      title: nullableString,
      poster: nullableString,
      width: z.number().int().nullable().optional(),
      height: z.number().int().nullable().optional(),
    }),
    z.object({ type: z.literal("code"), text: z.string(), language: nullableString }),
    z.object({ type: z.literal("divider") }),
    z.object({ type: z.literal("card"), blocks: z.array(blockSchema), link: linkTargetSchema.nullable().optional() }),
    z.object({
      type: z.literal("accordion"),
      items: z.array(z.object({ title: richTextSchema, blocks: z.array(blockSchema) })),
    }),
    z.object({
      type: z.literal("form"),
      action: nullableString,
      method: nullableString,
      submitLabel: nullableString,
      fields: z.array(
        z.object({
          name: z.string(),
          label: nullableString,
          inputType: z.string(),
          required: z.boolean().optional(),
          placeholder: nullableString,
          options: z.array(z.string()).optional(),
        }),
      ),
    }),
    z.object({ type: z.literal("html"), html: z.string(), text: z.string().optional(), reason: nullableString }),
  ]) as unknown as z.ZodType<Block>,
);

const KNOWN_TYPES = new Set([
  "heading", "paragraph", "list", "table", "quote", "image", "gallery", "button",
  "embed", "code", "divider", "card", "accordion", "form", "html",
]);

/** Known block types are validated strictly; unknown types are kept (never dropped silently). */
export const blockSchema: z.ZodType<Block> = z.lazy(() =>
  z.custom<Block>((value) => typeof value === "object" && value !== null && "type" in value).transform((value, ctx) => {
    const raw = value as Record<string, unknown>;
    if (!KNOWN_TYPES.has(String(raw.type))) {
      return { type: "unknown", originalType: String(raw.type), data: raw } as Block;
    }
    const parsed = knownBlockSchema.safeParse(raw);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) ctx.addIssue({ ...issue, path: issue.path } as never);
      return z.NEVER;
    }
    return parsed.data;
  }),
) as unknown as z.ZodType<Block>;

export const sectionTypeSchema = z.enum(["hero", "content", "cards", "faq", "testimonials", "gallery", "cta", "form", "generic"]);
export type SectionType = z.infer<typeof sectionTypeSchema>;

export const sectionSchema = z.object({
  id: z.string(),
  type: z.string().transform((t) => (sectionTypeSchema.options.includes(t as SectionType) ? (t as SectionType) : "generic")),
  blocks: z.array(blockSchema),
  source: z.object({ tag: z.string().optional(), id: nullableString, classes: z.array(z.string()).optional() }).optional(),
});
export type Section = z.infer<typeof sectionSchema>;

export type NavItem = {
  label: string;
  url: string | null;
  path: string | null;
  external: boolean;
  order: number;
  depth: number;
  type?: string;
  children: NavItem[];
};
export const navItemSchema: z.ZodType<NavItem> = z.lazy(() =>
  z.object({
    label: z.string(),
    url: z.string().nullable(),
    path: z.string().nullable(),
    external: z.boolean(),
    order: z.number().int(),
    depth: z.number().int(),
    type: z.string().optional(),
    children: z.array(navItemSchema),
  }),
);

export const pageSchema = z.object({
  schemaVersion,
  path: z.string().startsWith("/"),
  url: z.string(),
  title: z.string(),
  meta: z.object({
    title: nullableString,
    description: nullableString,
    canonical: nullableString,
    lang: nullableString,
    h1: nullableString,
    robots: nullableString,
    og: z
      .object({
        title: nullableString,
        description: nullableString,
        image: nullableString,
        imageUrl: nullableString,
        type: nullableString,
        url: nullableString,
      })
      .optional(),
    structuredData: z.array(z.unknown()).optional(),
  }),
  breadcrumbs: z.array(navItemSchema).optional(),
  sections: z.array(sectionSchema),
});
export type Page = z.infer<typeof pageSchema>;

export const manifestPageSchema = z.object({
  path: z.string().startsWith("/"),
  title: nullableString,
  originalUrl: nullableString,
  finalUrl: nullableString,
  canonical: nullableString,
  aliases: z.array(z.string()).optional(),
  dir: z.string().optional(),
  content: z.string(),
  images: nullableString,
});
export type ManifestPage = z.infer<typeof manifestPageSchema>;

export const manifestSchema = z.object({
  schemaVersion,
  sourceUrl: z.string(),
  crawledAt: nullableString,
  site: z.object({ name: nullableString, lang: nullableString, homePath: z.string().optional() }).optional(),
  pages: z.array(manifestPageSchema),
});
export type Manifest = z.infer<typeof manifestSchema>;

export const navigationSchema = z.object({
  schemaVersion,
  main: z.array(navItemSchema),
  footer: z.array(navItemSchema),
  logo: z
    .object({
      href: z.string(),
      path: nullableString,
      external: z.boolean(),
      label: nullableString,
      image: nullableString,
      imageUrl: nullableString,
      alt: nullableString,
    })
    .nullable()
    .optional(),
  cta: z.array(navItemSchema).optional(),
  menus: z.array(z.unknown()).optional(),
});
export type Navigation = z.infer<typeof navigationSchema>;
