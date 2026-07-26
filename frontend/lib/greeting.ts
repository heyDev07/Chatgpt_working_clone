import type { User } from "@/lib/types";

// Just the first word of full_name - "What can I help with, Devendra Kumar Singh?" reads
// worse than "What can I help with, Devendra?" for a page heading, and every other chatbot
// with a named greeting (ChatGPT included) uses a first name, not the full one.
export function greetingText(user: User | null | undefined): string {
  const firstName = user?.full_name?.trim().split(/\s+/)[0];
  return firstName ? `What can I help with, ${firstName}?` : "What can I help with?";
}
