"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type KeyboardEvent } from "react";

import { deleteConversation, updateConversation } from "@/lib/api/conversations";
import type { Conversation } from "@/lib/types";

export function ConversationItem({ conversation }: { conversation: Conversation }) {
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isActive = params.conversationId === conversation.id;

  const [isRenaming, setIsRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(conversation.title);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["conversations"] });

  const { mutate: remove } = useMutation({
    mutationFn: () => deleteConversation(conversation.id),
    onSuccess: () => {
      invalidate();
      if (isActive) router.push("/chat");
    },
  });

  const { mutate: togglePin } = useMutation({
    mutationFn: () => updateConversation(conversation.id, { is_pinned: !conversation.is_pinned }),
    onSuccess: invalidate,
  });

  const { mutate: toggleArchive } = useMutation({
    mutationFn: () => updateConversation(conversation.id, { is_archived: !conversation.is_archived }),
    onSuccess: () => {
      invalidate();
      if (isActive) router.push("/chat");
    },
  });

  const { mutate: rename } = useMutation({
    mutationFn: (title: string) => updateConversation(conversation.id, { title }),
    onSuccess: invalidate,
  });

  const commitRename = () => {
    const trimmed = titleDraft.trim();
    setIsRenaming(false);
    if (trimmed && trimmed !== conversation.title) {
      rename(trimmed);
    } else {
      setTitleDraft(conversation.title);
    }
  };

  const handleRenameKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") {
      setTitleDraft(conversation.title);
      setIsRenaming(false);
    }
  };

  if (isRenaming) {
    return (
      <input
        autoFocus
        value={titleDraft}
        onChange={(e) => setTitleDraft(e.target.value)}
        onKeyDown={handleRenameKeyDown}
        onBlur={commitRename}
        className="w-full rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none ring-1 ring-blue-500"
      />
    );
  }

  return (
    <div
      className={`group flex items-center justify-between rounded-lg px-2.5 py-2 text-sm ${
        isActive ? "bg-black/10 dark:bg-white/15" : "hover:bg-black/5 dark:hover:bg-white/10"
      }`}
    >
      <Link href={`/chat/${conversation.id}`} className="flex-1 flex items-center gap-1.5 min-w-0">
        {conversation.is_pinned && <Pin size={12} className="flex-shrink-0 opacity-50" />}
        <span className="truncate text-black/80 dark:text-white/80">{conversation.title}</span>
      </Link>
      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 flex-shrink-0 pl-1">
        <button
          onClick={(e) => {
            e.preventDefault();
            togglePin();
          }}
          aria-label={conversation.is_pinned ? "Unpin" : "Pin"}
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          {conversation.is_pinned ? <PinOff size={14} /> : <Pin size={14} />}
        </button>
        <button
          onClick={(e) => {
            e.preventDefault();
            setTitleDraft(conversation.title);
            setIsRenaming(true);
          }}
          aria-label="Rename"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Pencil size={14} />
        </button>
        <button
          onClick={(e) => {
            e.preventDefault();
            toggleArchive();
          }}
          aria-label={conversation.is_archived ? "Unarchive" : "Archive"}
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          {conversation.is_archived ? <ArchiveRestore size={14} /> : <Archive size={14} />}
        </button>
        <button
          onClick={(e) => {
            e.preventDefault();
            remove();
          }}
          aria-label="Delete"
          className="text-black/40 hover:text-red-500 dark:text-white/40"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
