"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { createTag, deleteTag, listTags } from "@/lib/api/tags";

export function TagFilterBar({
  selectedTagId,
  onSelect,
}: {
  selectedTagId: string | null;
  onSelect: (tagId: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const { data: tags } = useQuery({ queryKey: ["tags"], queryFn: listTags });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["tags"] });

  const { mutate: create } = useMutation({
    mutationFn: (name: string) => createTag(name),
    onSuccess: invalidate,
  });

  const { mutate: remove } = useMutation({
    mutationFn: (id: string) => deleteTag(id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const commitCreate = () => {
    const trimmed = newName.trim();
    setIsCreating(false);
    setNewName("");
    if (trimmed) create(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commitCreate();
    if (e.key === "Escape") {
      setIsCreating(false);
      setNewName("");
    }
  };

  if (!tags?.length && !isCreating) {
    return (
      <div className="flex items-center justify-between px-2">
        <span className="text-xs font-medium text-black/40 dark:text-white/40">Tags</span>
        <button
          onClick={() => setIsCreating(true)}
          aria-label="New tag"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Plus size={14} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 px-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-black/40 dark:text-white/40">Tags</span>
        <button
          onClick={() => setIsCreating(true)}
          aria-label="New tag"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tags?.map((tag) => (
          <button
            key={tag.id}
            onClick={() => onSelect(selectedTagId === tag.id ? null : tag.id)}
            className={`group flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ${
              selectedTagId === tag.id
                ? "bg-blue-600 text-white"
                : "bg-black/5 dark:bg-white/10 text-black/70 dark:text-white/70 hover:bg-black/10 dark:hover:bg-white/15"
            }`}
          >
            {tag.name}
            <span
              onClick={(e) => {
                e.stopPropagation();
                if (selectedTagId === tag.id) onSelect(null);
                remove(tag.id);
              }}
              className="opacity-0 group-hover:opacity-100"
            >
              <X size={10} />
            </span>
          </button>
        ))}
        {isCreating && (
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={commitCreate}
            placeholder="Tag name"
            className="w-24 rounded-full bg-black/5 dark:bg-white/10 px-2.5 py-1 text-xs outline-none ring-1 ring-blue-500"
          />
        )}
      </div>
    </div>
  );
}
