"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
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
        <span className="text-xs font-medium text-black/40 dark:text-white/40">
          {showArchived ? "Archived" : "Chats"}
        </span>
        <button
          onClick={() => setShowArchived((prev) => !prev)}
          className="text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          {showArchived ? "Show active" : "Show archived"}
        </button>
      </div>

      <div className="flex flex-col gap-0.5 px-1">
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
        {conversations?.map((conversation) => (
          <ConversationItem key={conversation.id} conversation={conversation} />
        ))}
      </div>
    </div>
  );
}
