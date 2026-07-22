"use client";

import { Check, Copy, Pencil, RotateCw, Sparkles } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import type { Message } from "@/lib/types";

import { MarkdownContent } from "./MarkdownContent";
import { StreamingCursor } from "./StreamingCursor";

export function MessageBubble({
  message,
  isStreaming,
  onRegenerate,
  onEdit,
}: {
  message: Message;
  isStreaming?: boolean;
  onRegenerate?: () => void;
  onEdit?: (content: string) => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const startEdit = () => {
    setDraft(message.content);
    setIsEditing(true);
  };

  const submitEdit = () => {
    const trimmed = draft.trim();
    setIsEditing(false);
    if (trimmed && trimmed !== message.content) {
      onEdit?.(trimmed);
    }
  };

  const handleEditKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitEdit();
    }
    if (e.key === "Escape") {
      setIsEditing(false);
    }
  };

  if (isUser) {
    if (isEditing) {
      return (
        <div className="flex justify-end">
          <div className="w-full max-w-[75%] rounded-3xl border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 px-4 py-2.5">
            <textarea
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleEditKeyDown}
              rows={Math.min(6, Math.max(1, draft.split("\n").length))}
              className="w-full resize-none bg-transparent text-[15px] leading-relaxed outline-none text-black dark:text-white"
            />
            <div className="mt-2 flex justify-end gap-2">
              <button
                onClick={() => setIsEditing(false)}
                className="rounded-full px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={submitEdit}
                className="rounded-full bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="group flex justify-end">
        <div className="flex flex-col items-end max-w-[75%]">
          <div className="rounded-3xl bg-neutral-100 dark:bg-neutral-800 px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words text-black dark:text-white">
            {message.content}
          </div>
          {onEdit && (
            <button
              onClick={startEdit}
              aria-label="Edit message"
              className="mt-1 flex items-center gap-1 text-xs text-black/40 hover:text-black opacity-0 group-hover:opacity-100 dark:text-white/40 dark:hover:text-white"
            >
              <Pencil size={12} />
              Edit
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="group flex gap-4">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500 text-white">
        <Sparkles size={16} />
      </div>
      <div className="flex-1 min-w-0 pt-1">
        <div className="text-[15px] leading-relaxed text-black/90 dark:text-white/90">
          <MarkdownContent content={message.content} />
          {isStreaming && <StreamingCursor />}
        </div>
        {!isStreaming && message.content && (
          <div className="mt-1 flex items-center gap-3 opacity-0 group-hover:opacity-100">
            <button
              onClick={handleCopy}
              aria-label="Copy message"
              className="flex items-center gap-1 text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? "Copied" : "Copy"}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                aria-label="Regenerate response"
                className="flex items-center gap-1 text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
              >
                <RotateCw size={13} />
                Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
