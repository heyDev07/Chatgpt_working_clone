"use client";

import { useEffect, useState } from "react";

import { fetchAttachmentBlobUrl } from "@/lib/api/attachments";

// Not a plain <img src={apiUrl}>: the content endpoint requires an Authorization header, which
// an <img> tag can't send - so this fetches the bytes itself and renders them as a blob URL.
export function AttachmentImage({ id, alt }: { id: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetchAttachmentBlobUrl(id)
      .then((blobUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        objectUrl = blobUrl;
        setUrl(blobUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  if (!url) {
    return <div className="h-40 w-40 animate-pulse rounded-xl bg-black/5 dark:bg-white/10" />;
  }

  // eslint-disable-next-line @next/next/no-img-element -- blob: URL, not eligible for next/image
  return <img src={url} alt={alt} className="max-h-64 rounded-xl object-cover" />;
}
