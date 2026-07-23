"use client";

import { useQuery } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { use } from "react";

import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { ApiError } from "@/lib/api/client";
import { getSharedConversation } from "@/lib/api/shared";

export default function SharedConversationPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);

  const { data, isLoading, error } = useQuery({
    queryKey: ["shared-conversation", token],
    queryFn: () => getSharedConversation(token),
    retry: false,
  });

  if (isLoading) {
    return (
      <main className="flex-1 flex items-center justify-center bg-white dark:bg-[#212121]">
        <p className="text-sm text-black/40 dark:text-white/40">Loading...</p>
      </main>
    );
  }

  if (error || !data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <main className="flex-1 flex flex-col items-center justify-center gap-2 bg-white dark:bg-[#212121] px-4">
        <p className="text-sm text-black/60 dark:text-white/60">
          {notFound ? "This shared link doesn't exist or is no longer active." : "Something went wrong."}
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-y-auto bg-white dark:bg-[#212121]">
      <div className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
        <div className="flex items-center gap-2 rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-xs text-black/50 dark:text-white/50">
          <MessageCircle size={14} />
          Shared conversation - read-only
        </div>

        <h1 className="text-2xl font-semibold text-black/90 dark:text-white/90">{data.title}</h1>

        <div className="flex flex-col gap-6">
          {data.messages.map((message, index) => (
            <div key={index} className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-black/40 dark:text-white/40">
                {message.role === "assistant" ? "Assistant" : message.role === "user" ? "User" : message.role}
              </span>
              <MarkdownContent content={message.content} />
            </div>
          ))}
          {data.messages.length === 0 && (
            <p className="text-sm text-black/40 dark:text-white/40">This conversation has no messages yet.</p>
          )}
        </div>
      </div>
    </main>
  );
}
