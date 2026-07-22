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
