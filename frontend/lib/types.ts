export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Tag {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  folder_id: string | null;
  tags: Tag[];
  title: string;
  provider: string;
  model: string;
  is_archived: boolean;
  is_pinned: boolean;
  system_prompt: string | null;
  temperature: number | null;
  max_tokens: number | null;
  top_p: number | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number | null;
  model: string | null;
  finish_reason: string | null;
  feedback?: "up" | "down" | null;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}
