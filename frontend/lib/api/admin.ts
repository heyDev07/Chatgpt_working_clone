import { apiFetch } from "@/lib/api/client";
import type { User } from "@/lib/types";

export interface DailyUsage {
  date: string;
  message_count: number;
  token_count: number;
}

export interface UserUsage {
  user_id: string;
  email: string;
  conversation_count: number;
  message_count: number;
  token_count: number;
}

export interface UsageOverview {
  total_users: number;
  total_conversations: number;
  total_messages: number;
  total_tokens: number;
  daily: DailyUsage[];
  top_users: UserUsage[];
}

export function listAllUsers(): Promise<User[]> {
  return apiFetch<User[]>("/admin/users");
}

export function getUsageAnalytics(days = 14): Promise<UsageOverview> {
  return apiFetch<UsageOverview>(`/admin/analytics/usage?days=${days}`);
}

export function setUserStatus(userId: string, isActive: boolean): Promise<User> {
  return apiFetch<User>(`/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function setUserRole(userId: string, role: "user" | "admin"): Promise<User> {
  return apiFetch<User>(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}
