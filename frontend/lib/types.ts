export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  role: string;
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
  share_token: string | null;
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

export interface Attachment {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

// Deliberately loose, not a single fixed shape - RAG document citations are
// {filename,document_id,score}, Deep Research's web citations are {title,url,snippet}. Both
// are genuinely different sources rendered by the same CitationList component, which branches
// on which fields are actually present rather than needing a shared schema.
export type Citation = Record<string, unknown>;

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number | null;
  model: string | null;
  finish_reason: string | null;
  feedback?: "up" | "down" | null;
  agent?: string | null;
  citations?: Citation[] | null;
  attachments?: Attachment[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

// Transient, live-turn-only - not persisted, cleared once the turn finishes and the real
// message is refetched (same scoping decision as RAG citations).
export interface ToolActivity {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "calling" | "success" | "error";
  output?: unknown;
  error?: string | null;
}

export interface Reminder {
  id: string;
  conversation_id: string | null;
  message: string;
  remind_at: string;
  is_delivered: boolean;
  created_at: string;
}

export interface Contact {
  id: string;
  name: string;
  relationship: string | null;
  notes: string | null;
  last_contact_at: string | null;
  created_at: string;
  updated_at: string;
}
