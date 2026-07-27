"use client";

// Parses the [title](url) links already embedded in a web-search-mode message's own content
// (see chat_service.py's _format_search_results) rather than needing a separate structured field
// from the backend - this derives naturally from message.content on every render, so it works
// the same on a fresh stream and after a page refresh, with no schema change needed. Rendered as
// its own row of real favicon chips, not markdown images: react-markdown's `img` renderer in
// MarkdownContent.tsx is shared by every image in the app (generated images, uploads), so
// forcing favicon-sized styling there would wrongly shrink everything else too.
const LINK_PATTERN = /\*\*\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)\*\*/g;

function extractSources(content: string): { title: string; url: string; domain: string }[] {
  const seen = new Set<string>();
  const sources: { title: string; url: string; domain: string }[] = [];
  for (const match of content.matchAll(LINK_PATTERN)) {
    const [, title, url] = match;
    try {
      const domain = new URL(url).hostname.replace(/^www\./, "");
      if (seen.has(domain)) continue;
      seen.add(domain);
      sources.push({ title, url, domain });
    } catch {
      // Malformed URL somehow - skip it rather than showing a broken favicon/link.
    }
  }
  return sources;
}

export function SearchSources({ content }: { content: string }) {
  const sources = extractSources(content);
  if (sources.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-black/40 dark:text-white/40">Sources:</span>
      {sources.map((source) => (
        <a
          key={source.domain}
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          title={source.title}
          className="flex items-center gap-1 rounded-full border border-black/10 bg-black/5 px-2 py-1 text-xs text-black/60 hover:bg-black/10 dark:border-white/10 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10"
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- external favicon service, not eligible for next/image */}
          <img
            src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
            alt=""
            className="h-3.5 w-3.5 flex-shrink-0 rounded-sm"
          />
          {source.domain}
        </a>
      ))}
    </div>
  );
}
