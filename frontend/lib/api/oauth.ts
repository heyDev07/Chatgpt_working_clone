import { apiFetch } from "@/lib/api/client";

export interface GoogleOAuthStatus {
  connected: boolean;
  google_email?: string;
  scopes?: string;
}

export function getGoogleOAuthAuthorizeUrl(): Promise<{ authorize_url: string }> {
  return apiFetch<{ authorize_url: string }>("/oauth/google/authorize");
}

export function getGoogleOAuthStatus(): Promise<GoogleOAuthStatus> {
  return apiFetch<GoogleOAuthStatus>("/oauth/google/status");
}

export function disconnectGoogleOAuth(): Promise<void> {
  return apiFetch<void>("/oauth/google/disconnect", { method: "POST" });
}

export function testGoogleOAuthConnection(): Promise<{
  email_address: string;
  total_messages: number;
  total_threads: number;
}> {
  return apiFetch("/oauth/google/test");
}
