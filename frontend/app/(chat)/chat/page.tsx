"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth/AuthContext";

export default function ChatPage() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
      <p className="text-lg">
        Welcome, <span className="font-semibold">{user?.full_name || user?.email}</span>
      </p>
      <p className="text-sm text-black/60 dark:text-white/60">
        The chat UI (sidebar, conversations, streaming) lands in the next milestone.
      </p>
      <button
        onClick={handleLogout}
        className="rounded-md border border-black/10 dark:border-white/15 px-4 py-2 text-sm"
      >
        Log out
      </button>
    </main>
  );
}
