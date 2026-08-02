import { fetchEventSource } from "@microsoft/fetch-event-source";

import { API_BASE_URL, getAccessToken } from "@/lib/api/client";

export interface ToolCallEventData {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultEventData {
  id: string;
  name: string;
  success: boolean;
  output: unknown;
  error: string | null;
}

export interface AgentEventData {
  name: string;
  label: string;
}

// Same shape as ToolCallEventData - kept as its own type since the two events mean different
// things to a caller (one is informational, the other blocks the turn on a decision).
export interface ToolConfirmationEventData {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

// Only ever sent once per orchestrate() call, right after decomposition - see
// orchestrator_service.py's docstring. Each step's own agent transition still arrives via the
// normal "agent" event as that subtask actually starts running.
export interface PlanEventData {
  steps: { agent: string; task: string }[];
}

export interface StreamCallbacks {
  onToken: (delta: string) => void;
  onAgent?: (event: AgentEventData) => void;
  onToolCall?: (event: ToolCallEventData) => void;
  onToolResult?: (event: ToolResultEventData) => void;
  onToolConfirmationRequired?: (event: ToolConfirmationEventData) => void;
  onPlan?: (event: PlanEventData) => void;
  onDone: (data: { message_id: string | null; finish_reason: string }) => void;
  onError: (message: string) => void;
}

function consumeStream(url: string, body: string | undefined, callbacks: StreamCallbacks, signal: AbortSignal) {
  return fetchEventSource(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken() ?? ""}`,
    },
    credentials: "include",
    body,
    signal,
    async onopen(response) {
      if (!response.ok) {
        throw new Error(`Stream failed to open: ${response.status}`);
      }
    },
    onmessage(ev) {
      if (ev.event === "token") {
        const data = JSON.parse(ev.data);
        callbacks.onToken(data.delta);
      } else if (ev.event === "agent") {
        callbacks.onAgent?.(JSON.parse(ev.data));
      } else if (ev.event === "tool_call") {
        callbacks.onToolCall?.(JSON.parse(ev.data));
      } else if (ev.event === "tool_result") {
        callbacks.onToolResult?.(JSON.parse(ev.data));
      } else if (ev.event === "tool_confirmation_required") {
        callbacks.onToolConfirmationRequired?.(JSON.parse(ev.data));
      } else if (ev.event === "plan") {
        callbacks.onPlan?.(JSON.parse(ev.data));
      } else if (ev.event === "done") {
        callbacks.onDone(JSON.parse(ev.data));
      } else if (ev.event === "error") {
        const data = JSON.parse(ev.data);
        callbacks.onError(data.message ?? "Stream error");
      }
    },
    onerror(err) {
      // Re-throwing prevents fetch-event-source's default infinite-retry behavior.
      callbacks.onError(err instanceof Error ? err.message : "Connection error");
      throw err;
    },
    openWhenHidden: true,
  });
}

export function streamMessage(
  conversationId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
  attachmentIds: string[] = [],
  agent?: string
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/messages`,
    JSON.stringify({ content, attachment_ids: attachmentIds, agent }),
    callbacks,
    signal
  );
}

export function regenerateMessage(
  conversationId: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/regenerate`,
    undefined,
    callbacks,
    signal
  );
}

export function editMessage(
  conversationId: string,
  messageId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
  attachmentIds: string[] = [],
  agent?: string
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/messages/${messageId}/edit`,
    JSON.stringify({ content, attachment_ids: attachmentIds, agent }),
    callbacks,
    signal
  );
}

// Explicit web-search mode - additive, separate endpoint from streamMessage above (never
// touches the LLM at all, see chat_service.py's stream_search docstring for why that's the
// entire point). No attachment_ids/agent - a search query is just text.
export function searchMessage(
  conversationId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/search`,
    JSON.stringify({ content }),
    callbacks,
    signal
  );
}

// Explicit "Agent" mode - decomposes into specialist subtasks and synthesizes one final answer,
// see orchestrator_service.py's docstring. Emits a "plan" event before anything else, then the
// normal token/tool_call/tool_result/agent events per subtask, same as streamMessage.
export function orchestrateMessage(
  conversationId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/orchestrate`,
    JSON.stringify({ content }),
    callbacks,
    signal
  );
}

// Explicit "Deep Research" mode - decomposes into research sub-questions (not specialists,
// unlike orchestrateMessage above), researches each sequentially with real web search/extraction,
// and synthesizes one long cited report - see research_service.py's docstring. Same event
// vocabulary as orchestrateMessage (a "plan" event first, then token/tool_call/tool_result/agent
// per sub-question), so no new callback types are needed here.
export function researchMessage(
  conversationId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/research`,
    JSON.stringify({ content }),
    callbacks,
    signal
  );
}
