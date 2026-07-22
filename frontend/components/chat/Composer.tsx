"use client";

import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

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
    <div className="px-4 pb-6 pt-2">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-[28px] border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 shadow-sm px-4 py-2.5">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Message..."
            rows={1}
            className="flex-1 resize-none bg-transparent py-1.5 text-[15px] outline-none disabled:opacity-50 placeholder:text-black/40 dark:placeholder:text-white/40 max-h-[200px]"
          />
          {disabled ? (
            <button
              onClick={onStop}
              className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black"
              aria-label="Stop generating"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!value.trim()}
              className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black disabled:opacity-30"
              aria-label="Send message"
            >
              <ArrowUp size={17} />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-xs text-black/30 dark:text-white/30">
          AI can make mistakes. Check important info.
        </p>
      </div>
    </div>
  );
}
