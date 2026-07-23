import { apiFetch } from "@/lib/api/client";
import type { Conversation, Tag } from "@/lib/types";

export function listTags(): Promise<Tag[]> {
  return apiFetch<Tag[]>("/tags");
}

export function createTag(name: string): Promise<Tag> {
  return apiFetch<Tag>("/tags", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function deleteTag(id: string): Promise<void> {
  return apiFetch<void>(`/tags/${id}`, { method: "DELETE" });
}

export function addConversationTag(conversationId: string, tagId: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${conversationId}/tags/${tagId}`, { method: "POST" });
}

export function removeConversationTag(conversationId: string, tagId: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${conversationId}/tags/${tagId}`, { method: "DELETE" });
}
