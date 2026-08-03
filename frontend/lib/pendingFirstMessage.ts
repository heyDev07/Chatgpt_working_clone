import type { ComposerMode } from "@/lib/composerMode";

// Handoff key for the first message sent from the landing page (app/(chat)/chat/page.tsx),
// which creates the conversation and navigates to /chat/{id} before anything is actually sent -
// streamMessage() needs a conversation id to already exist. ChatWindow reads this once on mount.
export const PENDING_FIRST_MESSAGE_KEY = "pendingFirstMessage";

export interface PendingFirstMessage {
  conversationId: string;
  content: string;
  attachmentIds: string[];
  mode: ComposerMode;
}

// Same handoff pattern, for the landing page's voice-mode button - there's no message content
// to send yet (voice mode listens for it), just a conversation id that didn't exist when the
// button was clicked. ChatWindow reads this once on mount, same as PENDING_FIRST_MESSAGE_KEY.
export const PENDING_VOICE_MODE_KEY = "pendingVoiceMode";

export interface PendingVoiceMode {
  conversationId: string;
}
