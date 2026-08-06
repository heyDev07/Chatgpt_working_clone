"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Tooltip } from "@/components/ui/Tooltip";
import { getConversation } from "@/lib/api/conversations";
import { confirmToolCall, setMessageFeedback, stopGeneration } from "@/lib/api/messages";
import { useAuth } from "@/lib/auth/AuthContext";
import type { ComposerMode } from "@/lib/composerMode";
import { greetingText } from "@/lib/greeting";
import {
  PENDING_FIRST_MESSAGE_KEY,
  PENDING_VOICE_MODE_KEY,
  type PendingFirstMessage,
  type PendingVoiceMode,
} from "@/lib/pendingFirstMessage";
import {
  editMessage,
  orchestrateMessage,
  regenerateMessage,
  researchMessage,
  searchMessage,
  streamMessage,
  type AgentEventData,
  type PlanEventData,
  type ToolCallEventData,
  type ToolConfirmationEventData,
  type ToolResultEventData,
} from "@/lib/api/stream";
import type { Message, ToolActivity } from "@/lib/types";

import { Composer } from "./Composer";
import { ConversationSettings } from "./ConversationSettings";
import { MessageList } from "./MessageList";
import { OrchestratorPlan } from "./OrchestratorPlan";
import { ToolConfirmationPrompt } from "./ToolConfirmationPrompt";
import { VoiceModeOverlay } from "./VoiceModeOverlay";

export function ChatWindow({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
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
  // A restricted tool (send_gmail, create_calendar_event) pauses the turn server-side until this
  // is resolved via confirmToolCall - see tool_confirmation.py's docstring for why that's a
  // separate request rather than something this stream connection can answer itself.
  const [pendingConfirmation, setPendingConfirmation] = useState<ToolConfirmationEventData | null>(null);
  const [isResolvingConfirmation, setIsResolvingConfirmation] = useState(false);
  // Only ever set for mode==="agent"/"research" turns (orchestrateMessage/researchMessage) -
  // see OrchestratorPlan.tsx.
  const [plan, setPlan] = useState<PlanEventData | null>(null);
  // Counts "agent" events since the current plan started, used as the active step index -
  // orchestrator steps have distinct agent names (findIndex by name would've worked), but
  // research_service.py's steps all share the same "deep_research" name (different sub-questions,
  // same persona), so position-in-arrival-order is the only thing that reliably identifies which
  // step is live. Both services emit exactly one "agent" event per step in order, so this stays
  // correct for either case.
  const [agentEventCount, setAgentEventCount] = useState(0);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  // Owned here rather than inside Composer - this component renders two separate <Composer>
  // instances (empty-state vs. has-messages, below) that React unmounts/remounts as the
  // conversation transitions between them, which would silently reset any state Composer owned
  // itself back to its default the moment the first message started sending.
  const [composerMode, setComposerMode] = useState<ComposerMode>("auto");
  // VoiceModeOverlay drives its own independent streamMessage() loop (see its docstring) -
  // this is just the toggle that shows/hides it.
  const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Batches SSE token deltas into one state update per animation frame instead of one per
  // token. Providers can stream many small chunks a second, and every setStreamingContent call
  // re-renders MarkdownContent, which fully re-parses the accumulated text into a fresh markdown
  // AST (react-markdown has no incremental/streaming parse mode) - updating on every single
  // token meant re-parsing and re-rendering the whole message far more often than the screen
  // can even paint, which is what actually read as "not smooth." Capping flushes to once per
  // frame bounds it to the display's real refresh rate, matching how production streaming chat
  // UIs (ChatGPT, Claude) avoid the same problem.
  const pendingDeltaRef = useRef("");
  const rafIdRef = useRef<number | null>(null);

  const cancelPendingFlush = () => {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    pendingDeltaRef.current = "";
  };

  const handleToken = (delta: string) => {
    pendingDeltaRef.current += delta;
    if (rafIdRef.current === null) {
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;
        const chunk = pendingDeltaRef.current;
        pendingDeltaRef.current = "";
        setStreamingContent((prev) => (prev ?? "") + chunk);
      });
    }
  };

  const handleAgent = (event: AgentEventData) => {
    setActiveAgent(event.name);
    setAgentEventCount((count) => count + 1);
  };

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

  const handleToolConfirmationRequired = (event: ToolConfirmationEventData) => setPendingConfirmation(event);

  const handlePlan = (event: PlanEventData) => {
    setPlan(event);
    setAgentEventCount(0);
  };

  const resolveConfirmation = async (approved: boolean) => {
    if (!pendingConfirmation) return;
    setIsResolvingConfirmation(true);
    try {
      await confirmToolCall(conversationId, pendingConfirmation.id, approved);
      setPendingConfirmation(null);
    } finally {
      setIsResolvingConfirmation(false);
    }
  };

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      cancelPendingFlush();
    };
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
    cancelPendingFlush();
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

  const handleSend = (content: string, attachmentIds: string[] = [], mode: ComposerMode = "auto") => {
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

    const callbacks = {
      onToken: handleToken,
      onAgent: handleAgent,
      onToolCall: handleToolCall,
      onToolResult: handleToolResult,
      onToolConfirmationRequired: handleToolConfirmationRequired,
      onPlan: handlePlan,
      onDone: async () => {
        // Awaited before clearing the streaming placeholder below - invalidateQueries alone
        // marks the cache stale but doesn't wait for the refetch, so clearing
        // streamingContent immediately left a real visible gap: the just-finished reply
        // would vanish (streaming state cleared) for one refetch round-trip before the
        // persisted version popped back in from the cache. Awaiting means the real message
        // is already in the cache by the time the placeholder disappears - one bubble
        // replaces the other in the same render, nothing goes blank in between.
        //
        // Wrapped in try/catch, not left to throw: consumeStream's onmessage calls onDone
        // without awaiting or catching it (fire-and-forget), so an unhandled rejection here -
        // e.g. a transient refetch failure - silently skips every line below, permanently
        // stuck on a "streaming" placeholder that never clears. Reproduced live: a real user
        // hit this and the reply just sat there mid-turn forever. The turn already succeeded
        // server-side by the time onDone fires - a failed refetch shouldn't undo that from the
        // user's perspective, it should just mean the next natural refetch catches up.
        try {
          await queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
        } catch {
          // best-effort - see comment above
        }
        setIsSending(false);
        setStreamingContent(null);
        setToolActivity([]);
        setActiveAgent(null);
        setPendingConfirmation(null);
        setPlan(null);
        setPendingMessages([]);
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
        if (isFirstMessage) scheduleTitleRefresh();
      },
      onError: (message: string) => {
        setIsSending(false);
        setStreamingContent(null);
        setToolActivity([]);
        setActiveAgent(null);
        setPendingConfirmation(null);
        setPlan(null);
        setError(message);
      },
    };

    // "search", "agent", and "research" are completely different endpoints (search never
    // touches the LLM, see chat_service.py's stream_search; agent decomposes into specialist
    // subtasks, see orchestrator_service.py; research decomposes into research sub-questions and
    // produces a cited report, see research_service.py) - everything else goes through the
    // normal message endpoint, with "auto" leaving the agent field unset so classify_agent()
    // picks as before.
    runStream((signal) =>
      mode === "search"
        ? searchMessage(conversationId, content, callbacks, signal)
        : mode === "agent"
          ? orchestrateMessage(conversationId, content, callbacks, signal)
          : mode === "research"
            ? researchMessage(conversationId, content, callbacks, signal)
            : streamMessage(conversationId, content, callbacks, signal, attachmentIds, mode === "auto" ? undefined : mode)
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
        // Genuine one-time sync from an external source (sessionStorage) into React state, not a
        // cascading-render anti-pattern - nothing in this render path could set this key itself.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setComposerMode(pending.mode);
        // Deferred a tick rather than called directly: handleSend's first act is a setState
        // (the optimistic pending-message append), and calling that synchronously inside an
        // effect body risks a cascading render - queueMicrotask moves it out of the effect's
        // own synchronous execution without any user-visible delay.
        queueMicrotask(() => handleSend(pending.content, pending.attachmentIds, pending.mode));
      }
    } catch {
      sessionStorage.removeItem(PENDING_FIRST_MESSAGE_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fires once per conversationId; handleSend is a fresh closure every render, not a meaningful dependency here
  }, [conversationId]);

  // Same handoff pattern as the pending-first-message effect above, for the landing page's voice
  // mode button - it has no conversation to open the overlay against until one exists, so it
  // creates one, stashes the id, and navigates here; this picks it up once on arrival.
  useEffect(() => {
    const raw = sessionStorage.getItem(PENDING_VOICE_MODE_KEY);
    if (!raw) return;
    try {
      const pending = JSON.parse(raw) as PendingVoiceMode;
      if (pending.conversationId === conversationId) {
        sessionStorage.removeItem(PENDING_VOICE_MODE_KEY);
        // eslint-disable-next-line react-hooks/set-state-in-effect -- genuine one-time sync from sessionStorage, not a cascading-render anti-pattern
        setIsVoiceModeOpen(true);
      }
    } catch {
      sessionStorage.removeItem(PENDING_VOICE_MODE_KEY);
    }
  }, [conversationId]);

  const handleRegenerate = () => {
    setIsRegenerating(true);

    runStream((signal) =>
      regenerateMessage(
        conversationId,
        {
          onToken: handleToken,
          onAgent: handleAgent,
          onToolCall: handleToolCall,
          onToolResult: handleToolResult,
          onToolConfirmationRequired: handleToolConfirmationRequired,
          onDone: async () => {
            // See handleSend's onDone for why this is wrapped - an unhandled rejection here
            // would otherwise skip every state-clearing line below and leave the UI stuck.
            try {
              await queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            } catch {
              // best-effort
            }
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setPendingConfirmation(null);
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (message) => {
            setIsSending(false);
            setIsRegenerating(false);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setPendingConfirmation(null);
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
          onToken: handleToken,
          onAgent: handleAgent,
          onToolCall: handleToolCall,
          onToolResult: handleToolResult,
          onToolConfirmationRequired: handleToolConfirmationRequired,
          onDone: async () => {
            // See handleSend's onDone for why this is wrapped - an unhandled rejection here
            // would otherwise skip every state-clearing line below and leave the UI stuck.
            try {
              await queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            } catch {
              // best-effort
            }
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setPendingConfirmation(null);
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
            if (isFirstMessage) scheduleTitleRefresh();
          },
          onError: (message) => {
            setIsSending(false);
            setEditingState(null);
            setStreamingContent(null);
            setToolActivity([]);
            setActiveAgent(null);
            setPendingConfirmation(null);
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
    // Aborting the local EventSource only stops *this tab* from watching - generation now
    // survives a closed connection by design (see chat_service.py's _stream_resilient), so an
    // explicit Stop click needs its own request to actually cancel the background generation,
    // not just detach from it. Fire-and-forget: whether or not it lands before generation
    // would've finished anyway, the UI's own state below already reflects "stopped."
    stopGeneration(conversationId).catch(() => {});
    abortRef.current?.abort();
    cancelPendingFlush();
    setIsSending(false);
    setIsRegenerating(false);
    setEditingState(null);
    setStreamingContent(null);
    setToolActivity([]);
    setActiveAgent(null);
    // Don't optimistically append here: the server persists whatever content had already
    // completed at the point of cancellation (same shielded finally block that protects a
    // genuine disconnect) - the refetch below picks that up.
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

  // No turn in flight and nothing sent yet - the heading and composer render as one centered
  // block in the middle of the screen (matching ChatGPT's empty-conversation layout), instead
  // of the heading centered in the space *above* a composer that's separately pinned to the
  // bottom - the two used to live in different flex children (MessageList vs. this component's
  // own trailing <Composer>), so they never actually appeared together as a single grouped
  // block the way a real empty state should. Once a message exists (or one is in flight), this
  // falls through to the normal transcript-plus-pinned-composer layout below.
  const isEmpty = messages.length === 0 && streamingContent === null;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-black/10 dark:border-white/10">
        <span className="truncate text-sm font-medium text-black/70 dark:text-white/70">
          {conversation?.title}
        </span>
        <Tooltip label="Conversation settings" side="bottom">
          <button
            onClick={() => setShowSettings(true)}
            aria-label="Conversation settings"
            className="flex-shrink-0 rounded-lg p-1.5 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
          >
            <Settings size={16} />
          </button>
        </Tooltip>
      </div>
      {isEmpty ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-4">
          <h1 className="text-3xl font-semibold text-black/80 dark:text-white/80">{greetingText(user)}</h1>
          <div className="w-full max-w-3xl">
            <Composer
              onSend={handleSend}
              onStop={handleStop}
              disabled={isSending}
              mode={composerMode}
              onModeChange={setComposerMode}
              onOpenVoiceMode={() => setIsVoiceModeOpen(true)}
            />
          </div>
          {error && (
            <div className="flex items-center gap-3 text-sm text-red-500">
              <span>{error}</span>
              <button onClick={handleRegenerate} className="underline hover:no-underline">
                Retry
              </button>
            </div>
          )}
        </div>
      ) : (
        <>
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
          {plan && streamingContent !== null && (
            <div className="mx-auto max-w-3xl w-full px-4 pb-1">
              <OrchestratorPlan plan={plan} activeStepIndex={agentEventCount - 1} />
            </div>
          )}
          {pendingConfirmation && (
            <ToolConfirmationPrompt
              call={pendingConfirmation}
              isResolving={isResolvingConfirmation}
              onApprove={() => resolveConfirmation(true)}
              onReject={() => resolveConfirmation(false)}
            />
          )}
          <Composer
            onSend={handleSend}
            onStop={handleStop}
            disabled={isSending}
            mode={composerMode}
            onModeChange={setComposerMode}
            onOpenVoiceMode={() => setIsVoiceModeOpen(true)}
          />
        </>
      )}
      {showSettings && conversation && (
        <ConversationSettings conversation={conversation} onClose={() => setShowSettings(false)} />
      )}
      {isVoiceModeOpen && (
        <VoiceModeOverlay conversationId={conversationId} onClose={() => setIsVoiceModeOpen(false)} />
      )}
    </div>
  );
}
