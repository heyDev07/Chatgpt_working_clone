"use client";

import { FileText } from "lucide-react";
import { useState } from "react";

import { fetchAttachmentBlobUrl } from "@/lib/api/attachments";

// Sibling to AttachmentImage.tsx, for the non-image attachment types added alongside it
// (PDF/DOCX/TXT/CSV/XLSX - see attachment_service.py's ALLOWED_DOCUMENT_CONTENT_TYPES). Unlike
// AttachmentImage, this doesn't eagerly fetch the file's bytes on mount - a document isn't
// rendered inline, so there's no reason to download it until the user actually wants to open it.
export function AttachmentFile({ id, filename }: { id: string; filename: string }) {
  const [isLoading, setIsLoading] = useState(false);

  const handleOpen = async () => {
    setIsLoading(true);
    try {
      const url = await fetchAttachmentBlobUrl(id);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      // Best-effort - matches this app's existing lack of granular inline error UI for
      // attachments (a failed upload just doesn't appear in the preview strip either).
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleOpen}
      disabled={isLoading}
      aria-label={`Open ${filename}`}
      className="flex max-w-[220px] items-center gap-2 rounded-xl border border-black/10 bg-black/5 px-3 py-2 text-left text-sm text-black/70 hover:bg-black/10 disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10"
    >
      <FileText size={16} className="flex-shrink-0" />
      <span className="truncate">{filename}</span>
    </button>
  );
}
