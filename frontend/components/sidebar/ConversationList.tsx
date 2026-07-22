"use client";

import { useQuery } from "@tanstack/react-query";

import { ConversationItem } from "@/components/sidebar/ConversationItem";
import { listConversations } from "@/lib/api/conversations";

export function ConversationList() {
  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  if (isLoading) {
    return <p className="px-3 py-2 text-sm text-black/40 dark:text-white/40">Loading...</p>;
  }

  if (!conversations || conversations.length === 0) {
    return <p className="px-3 py-2 text-sm text-black/40 dark:text-white/40">No conversations yet</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      {conversations.map((conversation) => (
        <ConversationItem key={conversation.id} conversation={conversation} />
      ))}
    </div>
  );
}
