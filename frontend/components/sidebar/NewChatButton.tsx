"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SquarePen } from "lucide-react";
import { useRouter } from "next/navigation";

import { createConversation } from "@/lib/api/conversations";

export function NewChatButton() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push(`/chat/${conversation.id}`);
    },
  });

  return (
    <button
      onClick={() => mutate()}
      disabled={isPending}
      className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-black/80 dark:text-white/80 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-50"
    >
      <SquarePen size={17} />
      New chat
    </button>
  );
}
