import { apiFetch } from "@/lib/api/client";
import type { Contact } from "@/lib/types";

export function listContacts(): Promise<Contact[]> {
  return apiFetch<Contact[]>("/contacts");
}

export function upsertContact(name: string, relationship?: string, note?: string): Promise<Contact> {
  return apiFetch<Contact>("/contacts", {
    method: "POST",
    body: JSON.stringify({ name, relationship: relationship ?? null, note: note ?? null }),
  });
}

export function deleteContact(id: string): Promise<void> {
  return apiFetch<void>(`/contacts/${id}`, { method: "DELETE" });
}
