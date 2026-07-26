"use client";

import { useEffect, useRef } from "react";

import type { Message, ToolActivity } from "@/lib/types";

import { MessageBubble } from "./MessageBubble";
import { ToolActivityList } from "./ToolActivityList";

// The empty-conversation state (no messages, no turn in flight) is handled entirely by
// ChatWindow, which renders the greeting and Composer together as one centered block - this
// component is only ever mounted once there's at least one message or a turn in progress, so it
// no longer needs its own empty-state branch.
export function MessageList({
  messages,
  streamingContent,
  toolActivity = [],
  activeAgent = null,
  onRegenerate,
  onEditMessage,
  onFeedback,
}: {
  messages: Message[];
  streamingContent: string | null;
  toolActivity?: ToolActivity[];
  activeAgent?: string | null;
  onRegenerate?: () => void;
  onEditMessage?: (messageId: string, content: string) => void;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, toolActivity, activeAgent]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            onRegenerate={
              streamingContent === null && index === messages.length - 1 && message.role === "assistant"
                ? onRegenerate
                : undefined
            }
            onEdit={
              streamingContent === null && message.role === "user" && onEditMessage
                ? (content) => onEditMessage(message.id, content)
                : undefined
            }
            onFeedback={
              streamingContent === null && message.role === "assistant" && onFeedback
                ? (feedback) => onFeedback(message.id, feedback)
                : undefined
            }
          />
        ))}
        {streamingContent !== null && <ToolActivityList activity={toolActivity} />}
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
              agent: activeAgent,
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
