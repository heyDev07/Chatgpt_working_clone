"use client";

import { Send, Square } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

export function Composer({
  onSend,
  onStop,
  disabled,
}: {
  onSend: (content: string) => void;
  onStop: () => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-black/10 dark:border-white/10 p-4">
      <div className="flex items-end gap-2 rounded-xl border border-black/10 dark:border-white/15 p-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Send a message..."
          rows={1}
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none disabled:opacity-50"
        />
        {disabled ? (
          <button
            onClick={onStop}
            className="rounded-lg bg-black/80 dark:bg-white/80 p-2 text-white dark:text-black"
            aria-label="Stop generating"
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim()}
            className="rounded-lg bg-blue-600 p-2 text-white disabled:opacity-40"
            aria-label="Send message"
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
