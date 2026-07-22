"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { getConversation } from "@/lib/api/conversations";
import { streamMessage } from "@/lib/api/stream";
import type { Message } from "@/lib/types";

import { Composer } from "./Composer";
import { MessageList } from "./MessageList";

export function ChatWindow({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient();
  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => getConversation(conversationId),
  });

  // Messages not yet reflected in the query cache (sent during the current streaming
  // turn). Combined with query data below rather than synced into state via an effect.
  const [pendingMessages, setPendingMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const messages = [...(conversation?.messages ?? []), ...pendingMessages];

  const handleSend = (content: string) => {
    setError(null);
    const userMessage: Message = {
      id: `temp-user-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      content,
      token_count: null,
      model: null,
      finish_reason: null,
      created_at: new Date().toISOString(),
    };
    setPendingMessages((prev) => [...prev, userMessage]);
    setStreamingContent("");
    setIsSending(true);

    const controller = new AbortController();
    abortRef.current = controller;

    streamMessage(
      conversationId,
      content,
      {
        onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
        onDone: () => {
          setIsSending(false);
          setStreamingContent(null);
          setPendingMessages([]);
          queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
        },
        onError: (message) => {
          setIsSending(false);
          setStreamingContent(null);
          setError(message);
        },
      },
      controller.signal
    ).catch(() => {
      // errors already surfaced via onError; swallow to avoid an unhandled rejection
    });
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsSending(false);
    setStreamingContent(null);
    // Don't optimistically append here: pendingMessages already holds the temp user message
    // from handleSend, and the server (verified to persist partial content on disconnect,
    // with finish_reason "cancelled") will return both the real user and assistant messages
    // on refetch. Appending an extra optimistic message on top of that duplicated both.
    setPendingMessages([]);
    queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-black/40 dark:text-white/40">
        Loading...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <MessageList messages={messages} streamingContent={streamingContent} />
      {error && <p className="px-4 py-2 text-sm text-red-500">{error}</p>}
      <Composer onSend={handleSend} onStop={handleStop} disabled={isSending} />
    </div>
  );
}
