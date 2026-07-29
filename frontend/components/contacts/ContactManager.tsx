"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { deleteContact, listContacts, upsertContact } from "@/lib/api/contacts";
import type { Contact } from "@/lib/types";

function ContactRow({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();

  const { mutate: remove } = useMutation({
    mutationFn: () => deleteContact(contact.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }),
  });

  return (
    <div className="group flex items-start justify-between gap-3 rounded-lg border border-black/10 dark:border-white/10 px-3 py-2.5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-black/80 dark:text-white/80">{contact.name}</span>
          {contact.relationship && (
            <span className="rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-black/50 dark:text-white/50">
              {contact.relationship}
            </span>
          )}
        </div>
        {contact.notes && (
          <p className="mt-1 whitespace-pre-line text-sm text-black/60 dark:text-white/60">{contact.notes}</p>
        )}
      </div>
      <button
        onClick={() => remove()}
        aria-label="Delete contact"
        className="flex-shrink-0 text-black/40 hover:text-red-500 dark:text-white/40 opacity-0 group-hover:opacity-100"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

function AddContactForm() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("");
  const [note, setNote] = useState("");

  const { mutate: add, isPending } = useMutation({
    mutationFn: () => upsertContact(name.trim(), relationship.trim() || undefined, note.trim() || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setName("");
      setRelationship("");
      setNote("");
      setIsOpen(false);
    },
  });

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-1.5 self-start rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
      >
        <Plus size={13} />
        Add contact
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-black/10 dark:border-white/10 p-3">
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name"
        className="rounded-md bg-black/5 dark:bg-white/10 px-2 py-1.5 text-sm outline-none"
      />
      <input
        value={relationship}
        onChange={(e) => setRelationship(e.target.value)}
        placeholder="Relationship (optional)"
        className="rounded-md bg-black/5 dark:bg-white/10 px-2 py-1.5 text-sm outline-none"
      />
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note (optional)"
        rows={2}
        className="resize-none rounded-md bg-black/5 dark:bg-white/10 px-2 py-1.5 text-sm outline-none"
      />
      <div className="flex gap-2">
        <button
          onClick={() => add()}
          disabled={!name.trim() || isPending}
          className="flex-1 rounded-lg bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black disabled:opacity-50"
        >
          {isPending ? "Saving..." : "Save"}
        </button>
        <button
          onClick={() => setIsOpen(false)}
          className="flex-1 rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export function ContactManager({ onClose }: { onClose: () => void }) {
  const { data: contacts, isLoading } = useQuery({
    queryKey: ["contacts"],
    queryFn: listContacts,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 shadow-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/10 dark:border-white/10">
          <div>
            <h2 className="text-sm font-semibold">Contacts</h2>
            <p className="text-xs text-black/50 dark:text-white/50 mt-0.5">
              People the assistant knows about, from conversations or added directly.
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
          <AddContactForm />
          {isLoading && <p className="text-sm text-black/40 dark:text-white/40">Loading...</p>}
          {!isLoading && (!contacts || contacts.length === 0) && (
            <p className="text-sm text-black/40 dark:text-white/40">
              No contacts yet - mention someone in chat, or add one above.
            </p>
          )}
          {contacts?.map((contact) => (
            <ContactRow key={contact.id} contact={contact} />
          ))}
        </div>
      </div>
    </div>
  );
}
