"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Folder as FolderIcon, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { createFolder, deleteFolder, listFolders, renameFolder, type Folder } from "@/lib/api/folders";

function FolderRow({
  folder,
  isSelected,
  onSelect,
}: {
  folder: Folder;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const queryClient = useQueryClient();
  const [isRenaming, setIsRenaming] = useState(false);
  const [draft, setDraft] = useState(folder.name);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["folders"] });

  const { mutate: rename } = useMutation({
    mutationFn: (name: string) => renameFolder(folder.id, name),
    onSuccess: invalidate,
  });

  const { mutate: remove } = useMutation({
    mutationFn: () => deleteFolder(folder.id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const commitRename = () => {
    const trimmed = draft.trim();
    setIsRenaming(false);
    if (trimmed && trimmed !== folder.name) rename(trimmed);
    else setDraft(folder.name);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") {
      setDraft(folder.name);
      setIsRenaming(false);
    }
  };

  if (isRenaming) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commitRename}
        className="w-full rounded-lg bg-black/5 dark:bg-white/10 px-2.5 py-1.5 text-sm outline-none ring-1 ring-blue-500"
      />
    );
  }

  return (
    <div
      className={`group flex items-center justify-between rounded-lg px-2.5 py-1.5 text-sm cursor-pointer ${
        isSelected ? "bg-black/10 dark:bg-white/15" : "hover:bg-black/5 dark:hover:bg-white/10"
      }`}
      onClick={onSelect}
    >
      <span className="flex-1 flex items-center gap-1.5 min-w-0 truncate text-black/80 dark:text-white/80">
        <FolderIcon size={13} className="flex-shrink-0 opacity-50" />
        <span className="truncate">{folder.name}</span>
      </span>
      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 flex-shrink-0 pl-1">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setDraft(folder.name);
            setIsRenaming(true);
          }}
          aria-label="Rename folder"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Pencil size={12} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            remove();
          }}
          aria-label="Delete folder"
          className="text-black/40 hover:text-red-500 dark:text-white/40"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}

export function FolderList({
  selectedFolderId,
  onSelect,
}: {
  selectedFolderId: string | null;
  onSelect: (folderId: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const { data: folders } = useQuery({ queryKey: ["folders"], queryFn: listFolders });

  const { mutate: create } = useMutation({
    mutationFn: (name: string) => createFolder(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["folders"] }),
  });

  const commitCreate = () => {
    const trimmed = newName.trim();
    setIsCreating(false);
    setNewName("");
    if (trimmed) create(trimmed);
  };

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between px-2">
        <span className="text-xs font-medium text-black/40 dark:text-white/40">Folders</span>
        <button
          onClick={() => setIsCreating(true)}
          aria-label="New folder"
          className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
        >
          <Plus size={14} />
        </button>
      </div>

      {isCreating && (
        <input
          autoFocus
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitCreate();
            if (e.key === "Escape") {
              setIsCreating(false);
              setNewName("");
            }
          }}
          onBlur={commitCreate}
          placeholder="Folder name"
          className="mx-1 rounded-lg bg-black/5 dark:bg-white/10 px-2.5 py-1.5 text-sm outline-none ring-1 ring-blue-500"
        />
      )}

      {folders?.map((folder) => (
        <FolderRow
          key={folder.id}
          folder={folder}
          isSelected={selectedFolderId === folder.id}
          onSelect={() => onSelect(selectedFolderId === folder.id ? null : folder.id)}
        />
      ))}
    </div>
  );
}
