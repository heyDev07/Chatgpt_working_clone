"use client";

import { Check, Copy, Sparkles } from "lucide-react";
import { useState } from "react";

import type { Message } from "@/lib/types";

import { MarkdownContent } from "./MarkdownContent";
import { StreamingCursor } from "./StreamingCursor";

export function MessageBubble({ message, isStreaming }: { message: Message; isStreaming?: boolean }) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-3xl bg-neutral-100 dark:bg-neutral-800 px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words text-black dark:text-white">
          {message.content}
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
          <button
            onClick={handleCopy}
            aria-label="Copy message"
            className="mt-1 flex items-center gap-1 text-xs text-black/40 hover:text-black opacity-0 group-hover:opacity-100 dark:text-white/40 dark:hover:text-white"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
    </div>
  );
}
