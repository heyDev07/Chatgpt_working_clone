import { apiFetch } from "@/lib/api/client";
import type { TokenResponse, User } from "@/lib/types";

export function registerUser(email: string, password: string, fullName?: string): Promise<User> {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName || undefined }),
  });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function fetchCurrentUser(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export function deleteAccount(password: string): Promise<void> {
  return apiFetch<void>("/auth/me", {
    method: "DELETE",
    body: JSON.stringify({ password }),
  });
}
