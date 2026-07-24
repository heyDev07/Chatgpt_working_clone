"use client";

import { ArrowUp, ImagePlus, Square, X } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { uploadAttachment } from "@/lib/api/attachments";

interface PendingAttachment {
  id: string;
  previewUrl: string;
  filename: string;
}

export function Composer({
  onSend,
  onStop,
  disabled,
}: {
  onSend: (content: string, attachmentIds: string[]) => void;
  onStop: () => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState<PendingAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  // Revoke any preview URLs still outstanding when the composer unmounts (e.g. navigating away
  // mid-upload) - otherwise those object URLs leak for the life of the tab.
  useEffect(() => {
    return () => {
      pending.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount-only cleanup
  }, []);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // allow re-selecting the same file later
    if (!files.length) return;

    setIsUploading(true);
    try {
      const uploaded = await Promise.all(
        files.map(async (file) => {
          const attachment = await uploadAttachment(file);
          return { id: attachment.id, previewUrl: URL.createObjectURL(file), filename: attachment.filename };
        })
      );
      setPending((prev) => [...prev, ...uploaded]);
    } catch {
      // Upload failures are rare (bad file type/size, network) and the file simply doesn't
      // appear in the preview strip - matches this composer's existing lack of granular
      // inline error UI elsewhere (e.g. send failures surface via ChatWindow's error banner).
    } finally {
      setIsUploading(false);
    }
  };

  const removeAttachment = (id: string) => {
    setPending((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  };

  const submit = () => {
    const trimmed = value.trim();
    if ((!trimmed && pending.length === 0) || disabled || isUploading) return;
    onSend(trimmed, pending.map((p) => p.id));
    setValue("");
    pending.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    setPending([]);
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
        <div className="rounded-[28px] border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 shadow-sm px-4 py-2.5">
          {pending.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {pending.map((p) => (
                <div key={p.id} className="group relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
                  <img src={p.previewUrl} alt={p.filename} className="h-16 w-16 rounded-lg object-cover" />
                  <button
                    onClick={() => removeAttachment(p.id)}
                    aria-label={`Remove ${p.filename}`}
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-black text-white opacity-0 group-hover:opacity-100 dark:bg-white dark:text-black"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isUploading}
              aria-label="Attach image"
              className="flex-shrink-0 rounded-full p-2 text-black/50 hover:bg-black/5 disabled:opacity-40 dark:text-white/50 dark:hover:bg-white/10"
            >
              <ImagePlus size={19} />
            </button>
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
                disabled={(!value.trim() && pending.length === 0) || isUploading}
                className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black disabled:opacity-30"
                aria-label="Send message"
              >
                <ArrowUp size={17} />
              </button>
            )}
          </div>
        </div>
        <p className="mt-2 text-center text-xs text-black/30 dark:text-white/30">
          AI can make mistakes. Check important info.
        </p>
      </div>
    </div>
  );
}
