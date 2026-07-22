"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { deleteConversation } from "@/lib/api/conversations";
import type { Conversation } from "@/lib/types";

export function ConversationItem({ conversation }: { conversation: Conversation }) {
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isActive = params.conversationId === conversation.id;

  const { mutate: remove } = useMutation({
    mutationFn: () => deleteConversation(conversation.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (isActive) router.push("/chat");
    },
  });

  return (
    <div
      className={`group flex items-center justify-between rounded-md px-3 py-2 text-sm ${
        isActive ? "bg-black/10 dark:bg-white/10" : "hover:bg-black/5 dark:hover:bg-white/5"
      }`}
    >
      <Link href={`/chat/${conversation.id}`} className="flex-1 truncate">
        {conversation.title}
      </Link>
      <button
        onClick={(e) => {
          e.preventDefault();
          remove();
        }}
        aria-label="Delete conversation"
        className="opacity-0 group-hover:opacity-100 text-black/40 hover:text-red-500 dark:text-white/40"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}
