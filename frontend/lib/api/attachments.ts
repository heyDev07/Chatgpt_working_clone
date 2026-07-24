import { apiFetch, API_BASE_URL, getAccessToken } from "@/lib/api/client";
import type { Attachment } from "@/lib/types";

export function uploadAttachment(file: File): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<Attachment>("/attachments/upload", {
    method: "POST",
    body: formData,
  });
}

// Not apiFetch: that always parses the response as JSON, but this endpoint returns raw image
// bytes. A plain <img src> can't carry the Authorization header this API requires, so the
// caller fetches the bytes itself and renders them as an object URL instead.
export async function fetchAttachmentBlobUrl(id: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/attachments/${id}/content`, {
    headers: { Authorization: `Bearer ${getAccessToken()}` },
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Failed to load attachment ${id}`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
