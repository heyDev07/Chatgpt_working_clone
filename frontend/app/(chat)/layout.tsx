"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth/AuthContext";

export default function ChatLayout({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
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

  return <>{children}</>;
}
