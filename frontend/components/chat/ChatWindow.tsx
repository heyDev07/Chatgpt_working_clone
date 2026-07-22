"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { getConversation } from "@/lib/api/conversations";
import { editMessage, regenerateMessage, streamMessage } from "@/lib/api/stream";
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
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [editingState, setEditingState] = useState<{ messageId: string; content: string } | null>(null);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const baseMessages = conversation?.messages ?? [];
  let visibleBase = baseMessages;
  if (isRegenerating && baseMessages.at(-1)?.role === "assistant") {
    // The last assistant reply is being replaced server-side - hide it from the base list so
    // the streaming placeholder doesn't render alongside a stale duplicate of what it replaces.
    visibleBase = baseMessages.slice(0, -1);
  } else if (editingState) {
    // Editing forks the conversation at this message: show everything up to and including it
    // (with its new content), and drop everything after - matching what the server will do.
    const index = baseMessages.findIndex((m) => m.id === editingState.messageId);
    if (index !== -1) {
      visibleBase = [
        ...baseMessages.slice(0, index),
        { ...baseMessages[index], content: editingState.content },
      ];
    }
  }
  const messages = [...visibleBase, ...pendingMessages];

  const runStream = (streamFn: (signal: AbortSignal) => Promise<void>) => {
    setError(null);
    setStreamingContent("");
    setIsSending(true);

    const controller = new AbortController();
    abortRef.current = controller;

    streamFn(controller.signal).catch(() => {
      // errors already surfaced via onError; swallow to avoid an unhandled rejection
    });
  };

  const handleSend = (content: string) => {
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

    runStream((signal) =>
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
        signal
      )
    );
  };

  const handleRegenerate = () => {
    setIsRegenerating(true);

    runStream((signal) =>
      regenerateMessage(
        conversationId,
        {
          onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
          onDone: () => {
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (message) => {
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            setError(message);
          },
        },
        signal
      )
    );
  };

  const handleEditMessage = (messageId: string, content: string) => {
    setEditingState({ messageId, content });

    runStream((signal) =>
      editMessage(
        conversationId,
        messageId,
        content,
        {
          onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
          onDone: () => {
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (message) => {
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            setError(message);
          },
        },
        signal
      )
    );
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsSending(false);
    setIsRegenerating(false);
    setEditingState(null);
    setStreamingContent(null);
    // Don't optimistically append here: the server (verified to persist partial content on
    // disconnect, with finish_reason "cancelled") will return the real messages on refetch.
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
      <MessageList
        messages={messages}
        streamingContent={streamingContent}
        onRegenerate={!isSending ? handleRegenerate : undefined}
        onEditMessage={!isSending ? handleEditMessage : undefined}
      />
      {error && (
        <div className="mx-auto max-w-3xl w-full px-4 pb-1 flex items-center gap-3 text-sm text-red-500">
          <span>{error}</span>
          <button onClick={handleRegenerate} className="underline hover:no-underline">
            Retry
          </button>
        </div>
      )}
      <Composer onSend={handleSend} onStop={handleStop} disabled={isSending} />
    </div>
  );
}
