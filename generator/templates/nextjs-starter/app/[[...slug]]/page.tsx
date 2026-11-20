import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Breadcrumbs from "@/components/layout/Breadcrumbs";
import ContentRenderer from "@/components/content/ContentRenderer";
import { getAllPaths, getPage } from "@/lib/content";
import { assetUrl, normalizePath, pathToSlug } from "@/lib/routes";

type Props = { params: Promise<{ slug?: string[] }> };

/** One route for every page of the archive – no per-page files. */
export function generateStaticParams() {
  return getAllPaths().map((path) => ({ slug: pathToSlug(path) }));
}

export const dynamicParams = false;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = getPage(normalizePath(slug));
  if (!page) return {};
  const ogImage = assetUrl(page.meta.og?.image);
  return {
    title: page.meta.title || page.title,
    description: page.meta.description ?? undefined,
    openGraph: {
      title: page.meta.og?.title ?? page.meta.title ?? page.title,
      description: page.meta.og?.description ?? page.meta.description ?? undefined,
      images: ogImage ? [ogImage] : undefined,
    },
  };
}

export default async function CatchAllPage({ params }: Props) {
  const { slug } = await params;
  const page = getPage(normalizePath(slug));
  if (!page) notFound();
  return (
    <article data-path={page.path}>
      {page.breadcrumbs && page.breadcrumbs.length > 1 ? <Breadcrumbs items={page.breadcrumbs} /> : null}
      <ContentRenderer sections={page.sections} />
    </article>
  );
}
