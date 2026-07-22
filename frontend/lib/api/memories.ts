import { apiFetch } from "@/lib/api/client";

export interface Memory {
  id: string;
  category: string;
  memory_text: string;
  importance: number;
  created_at: string;
  updated_at: string;
}

export function listMemories(): Promise<Memory[]> {
  return apiFetch<Memory[]>("/memories");
}

export function updateMemory(id: string, memory_text: string): Promise<Memory> {
  return apiFetch<Memory>(`/memories/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ memory_text }),
  });
}

export function deleteMemory(id: string): Promise<void> {
  return apiFetch<void>(`/memories/${id}`, { method: "DELETE" });
}
