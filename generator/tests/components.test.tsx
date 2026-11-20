import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { generate } from "../src/generate";
import { SAMPLE, tmpDir } from "./helpers";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} data-next-link="" {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ src, alt, unoptimized: _u, ...rest }: { src: string; alt: string; unoptimized?: boolean }) => <img src={src} alt={alt} {...rest} />,
}));

let ContentRenderer: typeof import("@/components/content/ContentRenderer").default;
let getPage: typeof import("@/lib/content").getPage;

beforeAll(async () => {
  const out = path.join(tmpDir(), "site");
  generate(SAMPLE, out);
  process.env.CONTENT_DIR = path.join(out, "content");
  ContentRenderer = (await import("@/components/content/ContentRenderer")).default;
  getPage = (await import("@/lib/content")).getPage;
});

function render(pagePath: string) {
  const page = getPage(pagePath)!;
  return renderToStaticMarkup(<ContentRenderer sections={page.sections} />);
}

describe("ContentRenderer", () => {
  it("renders sections in original order with section types", () => {
    const html = render("/");
    const types = [...html.matchAll(/data-section-type="(\w+)"/g)].map((m) => m[1]);
    expect(types).toEqual(["hero", "cards", "testimonials", "cta"]);
    expect(html.indexOf("Websites, die gefunden werden")).toBeLessThan(html.indexOf("Unsere Leistungen"));
  });

  it("keeps rich text marks and turns internal links into local routes", () => {
    const html = render("/");
    expect(html).toContain("<em>unabhängige</em>");
    expect(html).toContain("<strong>Webdesign</strong>");
    expect(html).toMatch(/<a href="\/leistungen\/seo" data-next-link="">SEO<\/a>/);
    expect(html).toMatch(/class="btn btn-primary"[^>]*>Leistungen ansehen|href="\/leistungen"[^>]*class="btn btn-primary"/);
  });

  it("groups cards into a grid and renders local images", () => {
    const html = render("/");
    expect(html.match(/rounded-card border border-line bg-surface p-6/g)).toHaveLength(2);
    expect(html).toMatch(/<img src="\/assets\/images\/[0-9a-f]{8}-webdesign\.png" alt="Webdesign Icon"/);
  });

  it("renders tables, nested lists, embeds, code, accordions, forms and fallbacks", () => {
    expect(render("/leistungen")).toContain("<th");
    const webdesign = render("/leistungen/webdesign");
    expect(webdesign).toMatch(/<ol>.*<li>Konzept<ul><li>Sitemap<\/li>/);
    expect(webdesign).toContain('src="https://www.youtube.com/embed/dQw4w9WgXcQ"');
    expect(webdesign).toContain('data-language="html"');
    const seo = render("/leistungen/seo");
    expect(seo).toContain("<details");
    expect(seo).toContain("Wie lange dauert SEO?");
    expect(seo).toContain('data-fallback="html"');
    expect(seo).toContain("<abbr");
    const kontakt = render("/kontakt");
    expect(kontakt).toContain('name="email"');
    expect(kontakt).toContain("Prototyp: Dieses Formular ist noch nicht angebunden.");
  });

  it("sanitizes fallback HTML and renders unknown blocks as text", async () => {
    const { default: BlockRenderer } = await import("@/components/content/BlockRenderer");
    const html = renderToStaticMarkup(
      <>
        <BlockRenderer block={{ type: "html", html: '<p onclick="x()">ok<script>alert(1)</script></p>' }} />
        <BlockRenderer block={{ type: "unknown", originalType: "timeline", data: { type: "timeline", entries: [{ text: "Gründung 2012" }] } }} />
      </>,
    );
    expect(html).toContain("<p>ok</p>");
    expect(html).not.toContain("script");
    expect(html).not.toContain("onclick");
    expect(html).toContain('data-fallback="timeline"');
    expect(html).toContain("Gründung 2012");
  });

  it("shows a visible placeholder for images that could not be downloaded", async () => {
    const { default: ImageBlock } = await import("@/components/content/ImageBlock");
    const html = renderToStaticMarkup(<ImageBlock image={{ type: "image", src: null, originalSrc: "https://x/y.png", alt: "Team" }} />);
    expect(html).toContain("Bild fehlt: Team");
  });
});
