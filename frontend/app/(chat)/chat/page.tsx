"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Composer } from "@/components/chat/Composer";
import { createConversation } from "@/lib/api/conversations";
import { PENDING_FIRST_MESSAGE_KEY } from "@/lib/pendingFirstMessage";

export default function ChatPage() {
  const router = useRouter();

  const { mutate, isPending } = useMutation({
    mutationFn: () => createConversation(),
  });

  const handleSend = (content: string, attachmentIds: string[]) => {
    mutate(undefined, {
      onSuccess: (conversation) => {
        sessionStorage.setItem(
          PENDING_FIRST_MESSAGE_KEY,
          JSON.stringify({ conversationId: conversation.id, content, attachmentIds })
        );
        router.push(`/chat/${conversation.id}`);
      },
    });
  };

  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-6">
      <h1 className="text-3xl font-semibold text-black/80 dark:text-white/80">What can I help with?</h1>
      <div className="w-full">
        <Composer onSend={handleSend} onStop={() => {}} disabled={isPending} />
      </div>
    </main>
  );
}
