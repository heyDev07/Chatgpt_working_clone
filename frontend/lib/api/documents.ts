import { apiFetch } from "@/lib/api/client";

export interface DocumentItem {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "pending" | "processing" | "ready" | "failed";
  chunk_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export function listDocuments(): Promise<DocumentItem[]> {
  return apiFetch<DocumentItem[]>("/documents");
}

export function getDocument(id: string): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(`/documents/${id}`);
}

export function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<DocumentItem>("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}
