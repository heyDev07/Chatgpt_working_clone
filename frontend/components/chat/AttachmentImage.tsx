"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchAttachmentBlobUrl } from "@/lib/api/attachments";

// Not a plain <img src={apiUrl}>: the content endpoint requires an Authorization header, which
// an <img> tag can't send - so this fetches the bytes itself and renders them as a blob URL.
export function AttachmentImage({ id, alt }: { id: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

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

  // Closeable with Escape, same as most chat apps' image viewers - only listens while actually
  // open, so this doesn't add a global keydown handler for every attachment on the page.
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!url) {
    return <div className="h-40 w-40 animate-pulse rounded-xl bg-black/5 dark:bg-white/10" />;
  }

  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- blob: URL, not eligible for next/image */}
      <img
        src={url}
        alt={alt}
        onClick={() => setIsOpen(true)}
        className="max-h-64 rounded-xl object-cover cursor-zoom-in transition-opacity hover:opacity-90"
      />
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
          onClick={() => setIsOpen(false)}
        >
          <button
            onClick={() => setIsOpen(false)}
            aria-label="Close"
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
          >
            <X size={20} />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element -- blob: URL, not eligible for next/image */}
          <img
            src={url}
            alt={alt}
            onClick={(e) => e.stopPropagation()}
            className="max-h-full max-w-full rounded-lg object-contain cursor-default"
          />
        </div>
      )}
    </>
  );
}
