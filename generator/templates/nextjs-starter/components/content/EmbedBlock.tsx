type Props = {
  provider: "youtube" | "vimeo" | "video" | "audio" | "map" | "iframe";
  url: string;
  title?: string | null;
  poster?: string | null;
};

/** Embedded media is referenced by its original URL (videos are not downloaded in v1). */
export default function EmbedBlock({ provider, url, title, poster }: Props) {
  if (provider === "video") {
    return <video src={url} poster={poster ?? undefined} controls className="w-full rounded-card" title={title ?? undefined} />;
  }
  if (provider === "audio") {
    return <audio src={url} controls className="w-full" title={title ?? undefined} />;
  }
  if (!/^https?:\/\//i.test(url)) return null;
  return (
    <div className={provider === "map" ? "aspect-[4/3] w-full" : "aspect-video w-full"}>
      <iframe
        src={url}
        title={title ?? provider}
        loading="lazy"
        className="h-full w-full rounded-card border-0"
        allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    </div>
  );
}
