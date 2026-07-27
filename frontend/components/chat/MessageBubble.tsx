"use client";

import { Check, Copy, Pencil, RotateCw, Sparkles, ThumbsDown, ThumbsUp, Volume2, VolumeX } from "lucide-react";
import { useEffect, useState, type KeyboardEvent } from "react";

import { agentLabel } from "@/lib/agents";
import { isSpeechSynthesisSupported, speakText, stopSpeaking } from "@/lib/speech";
import type { Message } from "@/lib/types";

import { AttachmentImage } from "./AttachmentImage";
import { MarkdownContent } from "./MarkdownContent";
import { SearchSources } from "./SearchSources";
import { StreamingCursor } from "./StreamingCursor";

export function MessageBubble({
  message,
  isStreaming,
  onRegenerate,
  onEdit,
  onFeedback,
}: {
  message: Message;
  isStreaming?: boolean;
  onRegenerate?: () => void;
  onEdit?: (content: string) => void;
  onFeedback?: (feedback: "up" | "down" | null) => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Stop this message's speech if it unmounts mid-utterance (e.g. switching conversations) -
  // otherwise the browser keeps reading a message that's no longer even on screen.
  useEffect(() => {
    return () => {
      if (isSpeaking) stopSpeaking();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount-only cleanup
  }, []);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const toggleSpeaking = () => {
    if (isSpeaking) {
      stopSpeaking();
      setIsSpeaking(false);
      return;
    }
    setIsSpeaking(true);
    speakText(message.content, () => setIsSpeaking(false));
  };

  const startEdit = () => {
    setDraft(message.content);
    setIsEditing(true);
  };

  const submitEdit = () => {
    const trimmed = draft.trim();
    setIsEditing(false);
    if (trimmed && trimmed !== message.content) {
      onEdit?.(trimmed);
    }
  };

  const handleEditKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitEdit();
    }
    if (e.key === "Escape") {
      setIsEditing(false);
    }
  };

  if (isUser) {
    if (isEditing) {
      return (
        <div className="flex justify-end">
          <div className="w-full max-w-[75%] rounded-3xl border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 px-4 py-2.5">
            <textarea
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleEditKeyDown}
              rows={Math.min(6, Math.max(1, draft.split("\n").length))}
              className="w-full resize-none bg-transparent text-[15px] leading-relaxed outline-none text-black dark:text-white"
            />
            <div className="mt-2 flex justify-end gap-2">
              <button
                onClick={() => setIsEditing(false)}
                className="rounded-full px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={submitEdit}
                className="rounded-full bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="group flex justify-end">
        <div className="flex flex-col items-end max-w-[75%]">
          {message.attachments && message.attachments.length > 0 && (
            <div className="mb-1.5 flex flex-wrap justify-end gap-2">
              {message.attachments.map((a) => (
                <AttachmentImage key={a.id} id={a.id} alt={a.filename} />
              ))}
            </div>
          )}
          {message.content && (
            <div className="rounded-3xl bg-neutral-100 dark:bg-neutral-800 px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words text-black dark:text-white">
              {message.content}
            </div>
          )}
          <div
            className={`mt-1 flex items-center gap-3 group-hover:opacity-100 ${
              isSpeaking ? "opacity-100" : "opacity-0"
            }`}
          >
            {onEdit && (
              <button
                onClick={startEdit}
                aria-label="Edit message"
                className="flex items-center gap-1 text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
              >
                <Pencil size={12} />
                Edit
              </button>
            )}
            {isSpeechSynthesisSupported() && message.content && (
              <button
                onClick={toggleSpeaking}
                aria-label={isSpeaking ? "Stop reading aloud" : "Read aloud"}
                className={`flex items-center gap-1 text-xs ${
                  isSpeaking
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
                }`}
              >
                {isSpeaking ? <VolumeX size={13} /> : <Volume2 size={13} />}
                {isSpeaking ? "Stop" : "Read aloud"}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const label = agentLabel(message.agent);

  return (
    <div className="group flex gap-4">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500 text-white">
        <Sparkles size={16} />
      </div>
      <div className="flex-1 min-w-0 pt-1">
        {label && label !== "General" && (
          <div className="mb-1.5 inline-flex items-center gap-1 rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5 text-[10px] font-medium text-black/50 dark:text-white/50">
            {/* "Web Search agent" would read oddly - it isn't an LLM persona at all, see
                agents.ts's AGENT_LABELS comment on why it shares this field/pill anyway. */}
            {label}
            {message.agent !== "web_search" && " agent"}
          </div>
        )}
        <div className="text-[15px] leading-relaxed text-black/90 dark:text-white/90">
          <MarkdownContent content={message.content} />
          {isStreaming && <StreamingCursor />}
        </div>
        {message.agent === "web_search" && <SearchSources content={message.content} />}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map((a) => (
              <AttachmentImage key={a.id} id={a.id} alt={a.filename} />
            ))}
          </div>
        )}
        {!isStreaming && message.content && (
          <div
            className={`mt-1 flex items-center gap-3 group-hover:opacity-100 ${
              message.feedback || isSpeaking ? "opacity-100" : "opacity-0"
            }`}
          >
            <button
              onClick={handleCopy}
              aria-label="Copy message"
              className="flex items-center gap-1 text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? "Copied" : "Copy"}
            </button>
            {isSpeechSynthesisSupported() && (
              <button
                onClick={toggleSpeaking}
                aria-label={isSpeaking ? "Stop reading aloud" : "Read aloud"}
                className={`flex items-center gap-1 text-xs ${
                  isSpeaking
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
                }`}
              >
                {isSpeaking ? <VolumeX size={13} /> : <Volume2 size={13} />}
                {isSpeaking ? "Stop" : "Read aloud"}
              </button>
            )}
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                aria-label="Regenerate response"
                className="flex items-center gap-1 text-xs text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
              >
                <RotateCw size={13} />
                Regenerate
              </button>
            )}
            {onFeedback && (
              <>
                <button
                  onClick={() => onFeedback(message.feedback === "up" ? null : "up")}
                  aria-label="Good response"
                  className={`text-xs ${
                    message.feedback === "up"
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
                  }`}
                >
                  <ThumbsUp size={13} fill={message.feedback === "up" ? "currentColor" : "none"} />
                </button>
                <button
                  onClick={() => onFeedback(message.feedback === "down" ? null : "down")}
                  aria-label="Bad response"
                  className={`text-xs ${
                    message.feedback === "down"
                      ? "text-red-500"
                      : "text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
                  }`}
                >
                  <ThumbsDown size={13} fill={message.feedback === "down" ? "currentColor" : "none"} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
