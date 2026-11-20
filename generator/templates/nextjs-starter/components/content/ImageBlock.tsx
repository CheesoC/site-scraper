import Image from "next/image";
import SmartLink from "@/components/SmartLink";
import { assetUrl, resolveHref } from "@/lib/routes";
import type { ImageBlock as ImageBlockType } from "@/lib/schema";
import RichText from "./RichText";

/** Local image from the archive. Missing downloads show a visible placeholder instead of disappearing. */
export default function ImageBlock({ image, className = "" }: { image: ImageBlockType; className?: string }) {
  const src = assetUrl(image.src);
  const picture = src ? (
    <Image
      src={src}
      alt={image.alt}
      width={image.width ?? 1200}
      height={image.height ?? 800}
      unoptimized
      className={`h-auto max-w-full rounded-card ${image.role === "icon" ? "w-12" : image.width ? "" : "w-full"}`}
    />
  ) : (
    <div role="img" aria-label={image.alt} title={`Bild nicht verfügbar: ${image.originalSrc}`} className="flex aspect-video w-full items-center justify-center rounded-card border border-dashed border-line bg-subtle text-sm text-muted">
      Bild fehlt: {image.alt || image.originalSrc}
    </div>
  );
  const linked = image.link ? <SmartLink href={resolveHref(image.link)}>{picture}</SmartLink> : picture;
  if (!image.caption || image.caption.length === 0) return <div className={className}>{linked}</div>;
  return (
    <figure className={className}>
      {linked}
      <figcaption className="mt-2 text-sm text-muted">
        <RichText nodes={image.caption} />
      </figcaption>
    </figure>
  );
}
