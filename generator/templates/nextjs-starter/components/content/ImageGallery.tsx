import type { ImageBlock as ImageBlockType } from "@/lib/schema";
import ImageBlock from "./ImageBlock";

export default function ImageGallery({ images }: { images: ImageBlockType[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
      {images.map((image, index) => (
        <ImageBlock key={`${index}-${image.originalSrc}`} image={image} />
      ))}
    </div>
  );
}
