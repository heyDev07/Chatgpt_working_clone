"use client";

import type { Citation } from "@/lib/types";

// Two genuinely different citation shapes land here - RAG document matches
// ({filename,document_id,score}, chat_service.py's _retrieve_document_context) and Deep
// Research's web sources ({title,url,snippet}, research_service.py) - branching on which fields
// are present avoids needing a shared schema or a `kind` discriminator neither backend path
// naturally produces.
function describeCitation(citation: Citation, index: number): { label: string; href: string | null } {
  if (typeof citation.url === "string") {
    const title = typeof citation.title === "string" && citation.title.trim() ? citation.title : citation.url;
    return { label: `${index + 1}. ${title}`, href: citation.url };
  }
  if (typeof citation.filename === "string") {
    return { label: `${index + 1}. ${citation.filename}`, href: null };
  }
  return { label: `${index + 1}. Source`, href: null };
}

export function CitationList({ citations }: { citations: Citation[] | null | undefined }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2 flex flex-col gap-1">
      <span className="text-xs text-black/40 dark:text-white/40">Sources</span>
      <ol className="flex flex-col gap-0.5">
        {citations.map((citation, index) => {
          const { label, href } = describeCitation(citation, index);
          return (
            <li key={href ?? label} className="truncate text-xs text-black/60 dark:text-white/60">
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {label}
                </a>
              ) : (
                <span>{label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
