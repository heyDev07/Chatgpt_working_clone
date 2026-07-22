import { Sparkles } from "lucide-react";

import type { Message } from "@/lib/types";

import { StreamingCursor } from "./StreamingCursor";

export function MessageBubble({ message, isStreaming }: { message: Message; isStreaming?: boolean }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-3xl bg-neutral-100 dark:bg-neutral-800 px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words text-black dark:text-white">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500 text-white">
        <Sparkles size={16} />
      </div>
      <div className="flex-1 min-w-0 pt-1 text-[15px] leading-relaxed whitespace-pre-wrap break-words text-black/90 dark:text-white/90">
        {message.content}
        {isStreaming && <StreamingCursor />}
      </div>
    </div>
  );
}
