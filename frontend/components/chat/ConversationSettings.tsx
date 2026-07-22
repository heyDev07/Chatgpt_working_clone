"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";

import { updateConversation } from "@/lib/api/conversations";
import type { ConversationDetail } from "@/lib/types";

export function ConversationSettings({
  conversation,
  onClose,
}: {
  conversation: ConversationDetail;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState(conversation.provider);
  const [model, setModel] = useState(conversation.model);
  const [systemPrompt, setSystemPrompt] = useState(conversation.system_prompt ?? "");
  const [temperature, setTemperature] = useState(conversation.temperature ?? 1);
  const [maxTokens, setMaxTokens] = useState(conversation.max_tokens?.toString() ?? "");
  const [topP, setTopP] = useState(conversation.top_p ?? 1);

  const { mutate: save, isPending } = useMutation({
    mutationFn: () =>
      updateConversation(conversation.id, {
        provider,
        model,
        system_prompt: systemPrompt,
        temperature,
        top_p: topP,
        ...(maxTokens ? { max_tokens: Number(maxTokens) } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 shadow-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/10 dark:border-white/10">
          <h2 className="text-sm font-semibold">Conversation settings</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-4 px-5 py-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-black/60 dark:text-white/60">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none"
            >
              <option value="openai">OpenAI-compatible</option>
              <option value="gemini">Gemini</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-black/60 dark:text-white/60">Model</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none font-mono"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-black/60 dark:text-white/60">System prompt</label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={3}
              placeholder="e.g. You are a concise, no-nonsense assistant."
              className="resize-none rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-black/30 dark:placeholder:text-white/30"
            />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-black/60 dark:text-white/60">Temperature</label>
              <span className="text-xs text-black/40 dark:text-white/40">{temperature.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-black/60 dark:text-white/60">Top P</label>
              <span className="text-xs text-black/40 dark:text-white/40">{topP.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={topP}
              onChange={(e) => setTopP(Number(e.target.value))}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-black/60 dark:text-white/60">Max tokens</label>
            <input
              type="number"
              min={1}
              max={32000}
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              placeholder="Provider default"
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-black/30 dark:placeholder:text-white/30"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-black/10 dark:border-white/10">
          <button
            onClick={onClose}
            className="rounded-full px-4 py-2 text-sm text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
          >
            Cancel
          </button>
          <button
            onClick={() => save()}
            disabled={isPending}
            className="rounded-full bg-black dark:bg-white px-4 py-2 text-sm text-white dark:text-black disabled:opacity-50"
          >
            {isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
