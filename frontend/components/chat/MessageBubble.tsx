import type { Message } from "@/lib/types";

import { StreamingCursor } from "./StreamingCursor";

export function MessageBubble({ message, isStreaming }: { message: Message; isStreaming?: boolean }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap break-words ${
          isUser ? "bg-blue-600 text-white" : "bg-black/5 dark:bg-white/10 text-black dark:text-white"
        }`}
      >
        {message.content}
        {isStreaming && <StreamingCursor />}
      </div>
    </div>
  );
}
