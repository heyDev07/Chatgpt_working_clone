"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldOff, UserCheck } from "lucide-react";

import { UsageAnalytics } from "@/components/admin/UsageAnalytics";
import { listAllUsers, setUserRole, setUserStatus } from "@/lib/api/admin";
import { useAuth } from "@/lib/auth/AuthContext";
import type { User } from "@/lib/types";

function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });

  const { mutate: toggleStatus, isPending: isTogglingStatus } = useMutation({
    mutationFn: () => setUserStatus(user.id, !user.is_active),
    onSuccess: invalidate,
  });

  const { mutate: toggleRole, isPending: isTogglingRole } = useMutation({
    mutationFn: () => setUserRole(user.id, user.role === "admin" ? "user" : "admin"),
    onSuccess: invalidate,
  });

  return (
    <tr className="border-b border-black/5 dark:border-white/10">
      <td className="px-3 py-2.5">
        <div className="text-sm text-black/80 dark:text-white/80">{user.email}</div>
        {user.full_name && <div className="text-xs text-black/40 dark:text-white/40">{user.full_name}</div>}
      </td>
      <td className="px-3 py-2.5">
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            user.role === "admin"
              ? "bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-400"
              : "bg-black/5 text-black/60 dark:bg-white/10 dark:text-white/60"
          }`}
        >
          {user.role}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            user.is_active
              ? "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-400"
              : "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400"
          }`}
        >
          {user.is_active ? "Active" : "Suspended"}
        </span>
      </td>
      <td className="px-3 py-2.5 text-xs text-black/40 dark:text-white/40">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <td className="px-3 py-2.5">
        {isSelf ? (
          <span className="text-xs text-black/30 dark:text-white/30">You</span>
        ) : (
          <div className="flex items-center gap-3">
            <button
              onClick={() => toggleRole()}
              disabled={isTogglingRole}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            >
              {user.role === "admin" ? "Revoke admin" : "Make admin"}
            </button>
            <button
              onClick={() => toggleStatus()}
              disabled={isTogglingStatus}
              className="flex items-center gap-1 text-xs text-black/50 hover:text-black dark:text-white/50 dark:hover:text-white disabled:opacity-50"
            >
              {user.is_active ? <ShieldOff size={12} /> : <UserCheck size={12} />}
              {user.is_active ? "Suspend" : "Reactivate"}
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: listAllUsers,
    enabled: currentUser?.role === "admin",
  });

  if (currentUser?.role !== "admin") {
    return (
      <main className="flex-1 flex items-center justify-center bg-white dark:bg-[#212121]">
        <p className="text-sm text-black/40 dark:text-white/40">You don&apos;t have access to this page.</p>
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-y-auto bg-white dark:bg-[#212121]">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-xl font-semibold text-black/90 dark:text-white/90 mb-4">Analytics</h1>
        <UsageAnalytics />

        <h1 className="text-xl font-semibold text-black/90 dark:text-white/90 mb-1">User management</h1>
        <p className="text-sm text-black/40 dark:text-white/40 mb-6">{users?.length ?? 0} accounts</p>

        <div className="overflow-x-auto rounded-lg border border-black/10 dark:border-white/10">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
                <th className="px-3 py-2 text-xs font-medium text-black/50 dark:text-white/50">User</th>
                <th className="px-3 py-2 text-xs font-medium text-black/50 dark:text-white/50">Role</th>
                <th className="px-3 py-2 text-xs font-medium text-black/50 dark:text-white/50">Status</th>
                <th className="px-3 py-2 text-xs font-medium text-black/50 dark:text-white/50">Joined</th>
                <th className="px-3 py-2 text-xs font-medium text-black/50 dark:text-white/50">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-sm text-black/40 dark:text-white/40">
                    Loading...
                  </td>
                </tr>
              )}
              {users?.map((user) => (
                <UserRow key={user.id} user={user} isSelf={user.id === currentUser.id} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
