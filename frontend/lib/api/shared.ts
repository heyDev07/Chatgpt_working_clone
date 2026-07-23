import { apiFetch } from "@/lib/api/client";

export interface SharedMessage {
  role: string;
  content: string;
  created_at: string;
}

export interface SharedConversation {
  title: string;
  messages: SharedMessage[];
  created_at: string;
}

export function getSharedConversation(token: string): Promise<SharedConversation> {
  return apiFetch<SharedConversation>(`/shared/${token}`);
}
