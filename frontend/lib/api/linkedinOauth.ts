import { apiFetch } from "@/lib/api/client";

export interface LinkedInOAuthStatus {
  connected: boolean;
  linkedin_name?: string;
  linkedin_email?: string;
  profile_picture_url?: string;
}

export function getLinkedInOAuthAuthorizeUrl(): Promise<{ authorize_url: string }> {
  return apiFetch<{ authorize_url: string }>("/oauth/linkedin/authorize");
}

export function getLinkedInOAuthStatus(): Promise<LinkedInOAuthStatus> {
  return apiFetch<LinkedInOAuthStatus>("/oauth/linkedin/status");
}

export function disconnectLinkedInOAuth(): Promise<void> {
  return apiFetch<void>("/oauth/linkedin/disconnect", { method: "POST" });
}
