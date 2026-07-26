"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Search } from "lucide-react";
import { useState } from "react";

import { ConversationItem } from "@/components/sidebar/ConversationItem";
import { listConversations } from "@/lib/api/conversations";

export function ConversationList({ folderId, tagId }: { folderId: string | null; tagId: string | null }) {
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations", { archived: showArchived, search, folderId, tagId }],
    queryFn: () =>
      listConversations({
        archived: showArchived,
        search: search || undefined,
        folderId: folderId || undefined,
        tagId: tagId || undefined,
      }),
  });

  // Pinned conversations get their own labeled section, same as folders/tags already do -
  // previously every conversation (pinned or not) rendered in one flat list under a single
  // "Chats" header, with only a small pin icon next to the title to tell them apart, unlike
  // the visually distinct grouping this is modeled on.
  const pinned = conversations?.filter((c) => c.is_pinned) ?? [];
  const unpinned = conversations?.filter((c) => !c.is_pinned) ?? [];

  return (
    <div className="flex flex-col gap-1">
      <div className="relative px-1 pb-1">
        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-black/40 dark:text-white/40" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search chats"
          className="w-full rounded-lg bg-black/5 dark:bg-white/10 pl-8 pr-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-black/40 dark:placeholder:text-white/40"
        />
      </div>

      <div className="flex items-center justify-between px-2">
        <span className="text-sm font-medium text-black/50 dark:text-white/50">
          {showArchived ? "Archived" : "Chats"}
        </span>
        {/* Was a bare text-xs link easy to miss entirely next to the section label - an icon +
            pill background makes it read as its own clickable control, and the highlighted
            state while active makes it obvious you're looking at a filtered (archived) view
            rather than the normal chat list. */}
        <button
          onClick={() => setShowArchived((prev) => !prev)}
          className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
            showArchived
              ? "bg-black/10 text-black/70 dark:bg-white/15 dark:text-white/80"
              : "text-black/40 hover:bg-black/5 hover:text-black dark:text-white/40 dark:hover:bg-white/10 dark:hover:text-white"
          }`}
        >
          {showArchived ? <ArchiveRestore size={13} /> : <Archive size={13} />}
          {showArchived ? "Show active" : "Show archived"}
        </button>
      </div>

      {isLoading && <p className="px-3 py-2 text-sm text-black/40 dark:text-white/40">Loading...</p>}
      {!isLoading && (!conversations || conversations.length === 0) && (
        <p className="px-3 py-2 text-sm text-black/40 dark:text-white/40">
          {search
            ? "No matching chats"
            : showArchived
              ? "No archived chats"
              : folderId
                ? "No chats in this folder"
                : tagId
                  ? "No chats with this tag"
                  : "No conversations yet"}
        </p>
      )}

      {pinned.length > 0 && (
        <div className="flex flex-col gap-0.5">
          <span className="px-2 pt-1 text-sm font-medium text-black/50 dark:text-white/50">Pinned</span>
          <div className="flex flex-col gap-0.5 px-1">
            {pinned.map((conversation) => (
              <ConversationItem key={conversation.id} conversation={conversation} />
            ))}
          </div>
        </div>
      )}

      {unpinned.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {pinned.length > 0 && (
            <span className="px-2 pt-2 text-sm font-medium text-black/50 dark:text-white/50">Recents</span>
          )}
          <div className="flex flex-col gap-0.5 px-1">
            {unpinned.map((conversation) => (
              <ConversationItem key={conversation.id} conversation={conversation} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
