"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getConversation } from "@/lib/api/conversations";
import { setMessageFeedback } from "@/lib/api/messages";
import { PENDING_FIRST_MESSAGE_KEY, type PendingFirstMessage } from "@/lib/pendingFirstMessage";
import {
  editMessage,
  regenerateMessage,
  streamMessage,
  type AgentEventData,
  type ToolCallEventData,
  type ToolResultEventData,
} from "@/lib/api/stream";
import type { Message, ToolActivity } from "@/lib/types";

import { Composer } from "./Composer";
import { ConversationSettings } from "./ConversationSettings";
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
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleAgent = (event: AgentEventData) => setActiveAgent(event.name);

  const handleToolCall = (event: ToolCallEventData) => {
    setToolActivity((prev) => [
      ...prev,
      { id: event.id, name: event.name, arguments: event.arguments, status: "calling" },
    ]);
  };

  const handleToolResult = (event: ToolResultEventData) => {
    setToolActivity((prev) =>
      prev.map((call) =>
        call.id === event.id
          ? { ...call, status: event.success ? "success" : "error", output: event.output, error: event.error }
          : call
      )
    );
  };

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

  // Title generation is fire-and-forget on the backend (see title_generation.py) and can finish
  // after the main reply's "done" event already fired and triggered the usual one-shot
  // invalidation below - without this, the sidebar/header would be stuck on the word-boundary
  // fallback title forever, never picking up the nicer AI-generated one. A single delayed
  // re-check a few seconds later is simpler than adding a push mechanism just for this.
  const scheduleTitleRefresh = () => {
    setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    }, 3000);
  };

  const runStream = (streamFn: (signal: AbortSignal) => Promise<void>) => {
    setError(null);
    setStreamingContent("");
    setToolActivity([]);
    setActiveAgent(null);
    setIsSending(true);

    const controller = new AbortController();
    abortRef.current = controller;

    streamFn(controller.signal).catch(() => {
      // errors already surfaced via onError; swallow to avoid an unhandled rejection
    });
  };

  const handleSend = (content: string, attachmentIds: string[] = []) => {
    const isFirstMessage = messages.length === 0;
    const userMessage: Message = {
      id: `temp-user-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      content,
      token_count: null,
      model: null,
      finish_reason: null,
      // Already-uploaded attachments have real ids by this point (Composer uploads on file
      // select, before send) - the optimistic bubble can render them via AttachmentImage same
      // as a persisted message would, just missing filename/size until the real one lands.
      attachments: attachmentIds.map((id) => ({ id, filename: "", content_type: "", size_bytes: 0, created_at: "" })),
      created_at: new Date().toISOString(),
    };
    setPendingMessages((prev) => [...prev, userMessage]);

    runStream((signal) =>
      streamMessage(
        conversationId,
        content,
        {
          onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
          onAgent: handleAgent,
          onToolCall: handleToolCall,
          onToolResult: handleToolResult,
          onDone: () => {
            setIsSending(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setPendingMessages([]);
            queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
            if (isFirstMessage) scheduleTitleRefresh();
          },
          onError: (message) => {
            setIsSending(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setError(message);
          },
        },
        signal,
        attachmentIds
      )
    );
  };

  // Picks up the first message handed off from the landing page (app/(chat)/chat/page.tsx),
  // which creates the conversation and navigates here *before* anything is actually sent, since
  // streamMessage() needs a conversation id to already exist. Guarded by conversationId matching
  // the stored entry, and the entry is removed immediately, so this only ever fires once for the
  // conversation it was meant for - including under React 18 StrictMode's double-invoke in dev,
  // where the second run just finds nothing left to send.
  useEffect(() => {
    const raw = sessionStorage.getItem(PENDING_FIRST_MESSAGE_KEY);
    if (!raw) return;
    try {
      const pending = JSON.parse(raw) as PendingFirstMessage;
      if (pending.conversationId === conversationId) {
        sessionStorage.removeItem(PENDING_FIRST_MESSAGE_KEY);
        // Deferred a tick rather than called directly: handleSend's first act is a setState
        // (the optimistic pending-message append), and calling that synchronously inside an
        // effect body risks a cascading render - queueMicrotask moves it out of the effect's
        // own synchronous execution without any user-visible delay.
        queueMicrotask(() => handleSend(pending.content, pending.attachmentIds));
      }
    } catch {
      sessionStorage.removeItem(PENDING_FIRST_MESSAGE_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fires once per conversationId; handleSend is a fresh closure every render, not a meaningful dependency here
  }, [conversationId]);

  const handleRegenerate = () => {
    setIsRegenerating(true);

    runStream((signal) =>
      regenerateMessage(
        conversationId,
        {
          onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
          onAgent: handleAgent,
          onToolCall: handleToolCall,
          onToolResult: handleToolResult,
          onDone: () => {
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (message) => {
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setError(message);
          },
        },
        signal
      )
    );
  };

  const handleEditMessage = (messageId: string, content: string) => {
    const isFirstMessage = messages[0]?.id === messageId;
    setEditingState({ messageId, content });

    runStream((signal) =>
      editMessage(
        conversationId,
        messageId,
        content,
        {
          onToken: (delta) => setStreamingContent((prev) => (prev ?? "") + delta),
          onAgent: handleAgent,
          onToolCall: handleToolCall,
          onToolResult: handleToolResult,
          onDone: () => {
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
            if (isFirstMessage) scheduleTitleRefresh();
          },
          onError: (message) => {
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setError(message);
          },
        },
        signal
      )
    );
  };

  const handleFeedback = (messageId: string, feedback: "up" | "down" | null) => {
    setMessageFeedback(conversationId, messageId, feedback).then(() => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
    });
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsSending(false);
    setIsRegenerating(false);
    setEditingState(null);
    setStreamingContent(null);
    setToolActivity([]);
    setActiveAgent(null);
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
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-black/10 dark:border-white/10">
        <span className="truncate text-sm font-medium text-black/70 dark:text-white/70">
          {conversation?.title}
        </span>
        <button
          onClick={() => setShowSettings(true)}
          aria-label="Conversation settings"
          className="flex-shrink-0 rounded-lg p-1.5 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
        >
          <Settings size={16} />
        </button>
      </div>
      <MessageList
        messages={messages}
        streamingContent={streamingContent}
        toolActivity={toolActivity}
        activeAgent={activeAgent}
        onRegenerate={!isSending ? handleRegenerate : undefined}
        onEditMessage={!isSending ? handleEditMessage : undefined}
        onFeedback={handleFeedback}
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
      {showSettings && conversation && (
        <ConversationSettings conversation={conversation} onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}
