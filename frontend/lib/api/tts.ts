import { API_BASE_URL, getAccessToken } from "@/lib/api/client";

// Not apiFetch() - that always calls response.json(), and this returns audio/wav bytes. Skips
// apiFetch's 401-refresh-and-retry dance for the same reason lib/api/stream.ts's consumeStream
// does - a mid-session token expiry here just means the next sentence fails to speak, not
// something worth the extra complexity to recover mid-utterance.
export async function synthesizeSpeech(text: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken() ?? ""}`,
    },
    credentials: "include",
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`TTS request failed: ${response.status}`);
  }
  return response.blob();
}
