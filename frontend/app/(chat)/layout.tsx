"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { ConversationList } from "@/components/sidebar/ConversationList";
import { NewChatButton } from "@/components/sidebar/NewChatButton";
import { useAuth } from "@/lib/auth/AuthContext";

export default function ChatLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p className="text-sm text-black/60 dark:text-white/60">Loading...</p>
      </main>
    );
  }

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      <aside className="w-64 flex-shrink-0 border-r border-black/10 dark:border-white/10 flex flex-col p-3 gap-3">
        <NewChatButton />
        <div className="flex-1 overflow-y-auto">
          <ConversationList />
        </div>
        <div className="border-t border-black/10 dark:border-white/10 pt-3 flex items-center justify-between gap-2">
          <span className="text-sm truncate">{user.full_name || user.email}</span>
          <button
            onClick={handleLogout}
            className="text-xs text-black/50 hover:text-black dark:text-white/50 dark:hover:text-white flex-shrink-0"
          >
            Log out
          </button>
        </div>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  );
}
