import { apiFetch } from "@/lib/api/client";
import type { Conversation, ConversationDetail } from "@/lib/types";

export function listConversations(options?: {
  archived?: boolean;
  search?: string;
  folderId?: string;
  tagId?: string;
}): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (options?.archived) params.set("archived", "true");
  if (options?.search) params.set("search", options.search);
  if (options?.folderId) params.set("folder_id", options.folderId);
  if (options?.tagId) params.set("tag_id", options.tagId);
  const query = params.toString();
  return apiFetch<Conversation[]>(`/conversations${query ? `?${query}` : ""}`);
}

export function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/conversations/${id}`);
}

export interface ConversationUpdatePayload {
  title?: string;
  is_pinned?: boolean;
  is_archived?: boolean;
  provider?: string;
  model?: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export function updateConversation(id: string, updates: ConversationUpdatePayload): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/conversations/${id}`, { method: "DELETE" });
}

export function setConversationFolder(id: string, folderId: string | null): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}/folder`, {
    method: "PATCH",
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export function shareConversation(id: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}/share`, { method: "POST" });
}

export function unshareConversation(id: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}/share`, { method: "DELETE" });
}
