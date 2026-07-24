// Handoff key for the first message sent from the landing page (app/(chat)/chat/page.tsx),
// which creates the conversation and navigates to /chat/{id} before anything is actually sent -
// streamMessage() needs a conversation id to already exist. ChatWindow reads this once on mount.
export const PENDING_FIRST_MESSAGE_KEY = "pendingFirstMessage";

export interface PendingFirstMessage {
  conversationId: string;
  content: string;
  attachmentIds: string[];
}
