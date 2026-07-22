"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { deleteMemory, listMemories, updateMemory, type Memory } from "@/lib/api/memories";

function MemoryRow({ memory }: { memory: Memory }) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(memory.memory_text);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["memories"] });

  const { mutate: save } = useMutation({
    mutationFn: (text: string) => updateMemory(memory.id, text),
    onSuccess: invalidate,
  });

  const { mutate: remove } = useMutation({
    mutationFn: () => deleteMemory(memory.id),
    onSuccess: invalidate,
  });

  const commit = () => {
    const trimmed = draft.trim();
    setIsEditing(false);
    if (trimmed && trimmed !== memory.memory_text) save(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      commit();
    }
    if (e.key === "Escape") {
      setDraft(memory.memory_text);
      setIsEditing(false);
    }
  };

  return (
    <div className="group flex items-start justify-between gap-3 rounded-lg border border-black/10 dark:border-white/10 px-3 py-2.5">
      <div className="flex-1 min-w-0">
        <span className="inline-block mb-1 rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-black/50 dark:text-white/50">
          {memory.category}
        </span>
        {isEditing ? (
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={commit}
            rows={2}
            className="w-full resize-none rounded-md bg-black/5 dark:bg-white/10 px-2 py-1.5 text-sm outline-none ring-1 ring-blue-500"
          />
        ) : (
          <p className="text-sm text-black/80 dark:text-white/80">{memory.memory_text}</p>
        )}
      </div>
      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 flex-shrink-0">
        <button
          onClick={() => setIsEditing(true)}
          aria-label="Edit memory"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Pencil size={14} />
        </button>
        <button
          onClick={() => remove()}
          aria-label="Delete memory"
          className="text-black/40 hover:text-red-500 dark:text-white/40"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export function MemoryManager({ onClose }: { onClose: () => void }) {
  const { data: memories, isLoading } = useQuery({
    queryKey: ["memories"],
    queryFn: listMemories,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 shadow-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/10 dark:border-white/10">
          <div>
            <h2 className="text-sm font-semibold">Saved memories</h2>
            <p className="text-xs text-black/50 dark:text-white/50 mt-0.5">
              Things the assistant has remembered about you across conversations.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-2 px-5 py-4">
          {isLoading && <p className="text-sm text-black/40 dark:text-white/40">Loading...</p>}
          {!isLoading && (!memories || memories.length === 0) && (
            <p className="text-sm text-black/40 dark:text-white/40">
              No memories yet - they build up automatically as you chat.
            </p>
          )}
          {memories?.map((memory) => (
            <MemoryRow key={memory.id} memory={memory} />
          ))}
        </div>
      </div>
    </div>
  );
}
