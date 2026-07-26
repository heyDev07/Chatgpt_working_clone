"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArchiveRestore,
  FolderInput,
  MessageSquare,
  Pencil,
  Pin,
  PinOff,
  Tag as TagIcon,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type ChangeEvent, type KeyboardEvent } from "react";

import { Tooltip } from "@/components/ui/Tooltip";
import { deleteConversation, setConversationFolder, updateConversation } from "@/lib/api/conversations";
import { listFolders } from "@/lib/api/folders";
import { addConversationTag, listTags, removeConversationTag } from "@/lib/api/tags";
import type { Conversation } from "@/lib/types";

export function ConversationItem({ conversation }: { conversation: Conversation }) {
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isActive = params.conversationId === conversation.id;

  const [isRenaming, setIsRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(conversation.title);
  const [isMovingFolder, setIsMovingFolder] = useState(false);
  const [isTagging, setIsTagging] = useState(false);

  const { data: folders } = useQuery({ queryKey: ["folders"], queryFn: listFolders, enabled: isMovingFolder });
  const { data: allTags } = useQuery({ queryKey: ["tags"], queryFn: listTags, enabled: isTagging });

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

  const { mutate: moveToFolder } = useMutation({
    mutationFn: (folderId: string | null) => setConversationFolder(conversation.id, folderId),
    onSuccess: invalidate,
  });

  const handleFolderChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setIsMovingFolder(false);
    moveToFolder(e.target.value || null);
  };

  const { mutate: addTag } = useMutation({
    mutationFn: (tagId: string) => addConversationTag(conversation.id, tagId),
    onSuccess: invalidate,
  });

  const { mutate: removeTag } = useMutation({
    mutationFn: (tagId: string) => removeConversationTag(conversation.id, tagId),
    onSuccess: invalidate,
  });

  const toggleTag = (tagId: string) => {
    if (conversation.tags.some((t) => t.id === tagId)) removeTag(tagId);
    else addTag(tagId);
  };

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

  if (isMovingFolder) {
    return (
      <select
        autoFocus
        defaultValue={conversation.folder_id ?? ""}
        onChange={handleFolderChange}
        onBlur={() => setIsMovingFolder(false)}
        className="w-full rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none ring-1 ring-blue-500"
      >
        <option value="">No folder</option>
        {folders?.map((folder) => (
          <option key={folder.id} value={folder.id}>
            {folder.name}
          </option>
        ))}
      </select>
    );
  }

  if (isTagging) {
    return (
      <div className="w-full rounded-lg bg-black/5 dark:bg-white/10 px-2 py-2 text-sm ring-1 ring-blue-500 flex flex-col gap-0.5">
        {!allTags?.length && <p className="px-1 py-1 text-xs text-black/40 dark:text-white/40">No tags yet</p>}
        {allTags?.map((tag) => {
          const isOn = conversation.tags.some((t) => t.id === tag.id);
          return (
            <button
              key={tag.id}
              onClick={() => toggleTag(tag.id)}
              className={`flex items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-black/5 dark:hover:bg-white/10 ${
                isOn ? "text-black dark:text-white" : "text-black/40 dark:text-white/40"
              }`}
            >
              <TagIcon size={12} />
              {tag.name}
            </button>
          );
        })}
        <button
          onClick={() => setIsTagging(false)}
          className="mt-1 self-end text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          Done
        </button>
      </div>
    );
  }

  return (
    <div
      className={`group flex items-center justify-between rounded-lg px-2.5 py-2 text-sm ${
        isActive ? "bg-black/10 dark:bg-white/15" : "hover:bg-black/5 dark:hover:bg-white/10"
      }`}
    >
      <Link href={`/chat/${conversation.id}`} className="flex-1 flex flex-col min-w-0">
        {/* Tags used to render inline after the title in the same flex row - the title span had
            no min-w-0 and the tags span was flex-shrink-0, so neither would ever yield width to
            the other, meaning `truncate` never actually engaged on either one: the row just
            overflowed, pushing tag text into the title and the hover action icons. Splitting
            tags onto their own line as separate pills sidesteps that flex math entirely instead
            of trying to get the shrink/truncate arithmetic right on a single cramped row. */}
        <span className="flex items-center gap-2 min-w-0">
          {conversation.is_pinned ? (
            <Pin size={13} className="flex-shrink-0 fill-current opacity-60" />
          ) : (
            <MessageSquare size={13} className="flex-shrink-0 opacity-40" />
          )}
          <span className="min-w-0 truncate text-black/80 dark:text-white/80">{conversation.title}</span>
        </span>
        {conversation.tags.length > 0 && (
          <span className="ml-[21px] mt-0.5 flex flex-wrap gap-1">
            {conversation.tags.map((t) => (
              <span
                key={t.id}
                className="truncate rounded-full bg-black/5 px-1.5 py-0.5 text-[10px] text-black/50 dark:bg-white/10 dark:text-white/50"
              >
                {t.name}
              </span>
            ))}
          </span>
        )}
      </Link>
      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 flex-shrink-0 pl-1">
        <Tooltip label={conversation.is_pinned ? "Unpin" : "Pin"}>
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
        </Tooltip>
        <Tooltip label="Rename">
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
        </Tooltip>
        <Tooltip label="Move to folder">
          <button
            onClick={(e) => {
              e.preventDefault();
              setIsMovingFolder(true);
            }}
            aria-label="Move to folder"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
          >
            <FolderInput size={14} />
          </button>
        </Tooltip>
        <Tooltip label="Edit tags">
          <button
            onClick={(e) => {
              e.preventDefault();
              setIsTagging(true);
            }}
            aria-label="Edit tags"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
          >
            <TagIcon size={14} />
          </button>
        </Tooltip>
        <Tooltip label={conversation.is_archived ? "Unarchive" : "Archive"}>
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
        </Tooltip>
        <Tooltip label="Delete">
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
        </Tooltip>
      </div>
    </div>
  );
}
