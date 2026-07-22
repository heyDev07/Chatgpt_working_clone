"use client";

import { useEffect, useRef } from "react";

import type { Message } from "@/lib/types";

import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  streamingContent,
}: {
  messages: Message[];
  streamingContent: string | null;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4">
      {messages.length === 0 && streamingContent === null && (
        <p className="text-center text-sm text-black/40 dark:text-white/40 mt-8">Start the conversation</p>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {streamingContent !== null && (
        <MessageBubble
          message={{
            id: "streaming",
            conversation_id: "",
            role: "assistant",
            content: streamingContent,
            token_count: null,
            model: null,
            finish_reason: null,
            created_at: new Date().toISOString(),
          }}
          isStreaming
        />
      )}
      <div ref={bottomRef} />
    </div>
  );
}
