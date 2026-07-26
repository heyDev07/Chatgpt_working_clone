import { apiFetch } from "@/lib/api/client";
import type { Reminder } from "@/lib/types";

export function listReminders(due = false): Promise<Reminder[]> {
  return apiFetch<Reminder[]>(`/reminders${due ? "?due=true" : ""}`);
}

export function createReminder(message: string, remindAt: string, conversationId?: string): Promise<Reminder> {
  return apiFetch<Reminder>("/reminders", {
    method: "POST",
    body: JSON.stringify({ message, remind_at: remindAt, conversation_id: conversationId ?? null }),
  });
}

export function deleteReminder(id: string): Promise<void> {
  return apiFetch<void>(`/reminders/${id}`, { method: "DELETE" });
}
