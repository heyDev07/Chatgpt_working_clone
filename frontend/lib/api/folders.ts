import { apiFetch } from "@/lib/api/client";

export interface Folder {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export function listFolders(): Promise<Folder[]> {
  return apiFetch<Folder[]>("/folders");
}

export function createFolder(name: string): Promise<Folder> {
  return apiFetch<Folder>("/folders", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function renameFolder(id: string, name: string): Promise<Folder> {
  return apiFetch<Folder>(`/folders/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function deleteFolder(id: string): Promise<void> {
  return apiFetch<void>(`/folders/${id}`, { method: "DELETE" });
}
