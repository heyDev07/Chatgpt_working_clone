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

export interface StreamCallbacks {
  onToken: (delta: string) => void;
  onToolCall?: (event: ToolCallEventData) => void;
  onToolResult?: (event: ToolResultEventData) => void;
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
      } else if (ev.event === "tool_call") {
        callbacks.onToolCall?.(JSON.parse(ev.data));
      } else if (ev.event === "tool_result") {
        callbacks.onToolResult?.(JSON.parse(ev.data));
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
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/messages`,
    JSON.stringify({ content }),
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
  signal: AbortSignal
): Promise<void> {
  return consumeStream(
    `${API_BASE_URL}/conversations/${conversationId}/messages/${messageId}/edit`,
    JSON.stringify({ content }),
    callbacks,
    signal
  );
}
