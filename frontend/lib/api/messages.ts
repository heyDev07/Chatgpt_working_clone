import { apiFetch } from "@/lib/api/client";
import type { Message } from "@/lib/types";

export function setMessageFeedback(
  conversationId: string,
  messageId: string,
  feedback: "up" | "down" | null
): Promise<Message> {
  return apiFetch<Message>(`/conversations/${conversationId}/messages/${messageId}`, {
    method: "PATCH",
    body: JSON.stringify({ feedback }),
  });
}

// Separate from just aborting the client-side EventSource: generation now survives the SSE
// connection closing (so an accidental disconnect doesn't silently discard the reply), which
// means an explicit "Stop" click needs its own signal to actually cancel the background
// generation rather than just stopping the client from watching it.
export function stopGeneration(conversationId: string): Promise<{ stopped: boolean }> {
  return apiFetch<{ stopped: boolean }>(`/conversations/${conversationId}/stop`, { method: "POST" });
}
