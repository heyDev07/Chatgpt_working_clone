import { apiFetch } from "@/lib/api/client";
import type { User } from "@/lib/types";

export function listAllUsers(): Promise<User[]> {
  return apiFetch<User[]>("/admin/users");
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
