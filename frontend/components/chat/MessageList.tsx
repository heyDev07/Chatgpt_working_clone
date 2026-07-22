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

  if (messages.length === 0 && streamingContent === null) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <h1 className="text-3xl font-semibold text-black/80 dark:text-white/80">What can I help with?</h1>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
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
    </div>
  );
}
