"use client";

import { Check, Loader2, Wrench, X } from "lucide-react";

import type { ToolActivity } from "@/lib/types";

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join(", ");
}

export function ToolActivityList({ activity }: { activity: ToolActivity[] }) {
  if (activity.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      {activity.map((call) => (
        <div
          key={call.id}
          className="flex flex-wrap items-center gap-2 rounded-lg border border-black/10 dark:border-white/10 px-3 py-2 text-xs text-black/60 dark:text-white/60 w-fit max-w-full"
        >
          {call.status === "calling" && <Loader2 size={13} className="flex-shrink-0 animate-spin" />}
          {call.status === "success" && (
            <Check size={13} className="flex-shrink-0 text-green-600 dark:text-green-500" />
          )}
          {call.status === "error" && <X size={13} className="flex-shrink-0 text-red-500" />}
          <Wrench size={13} className="flex-shrink-0 opacity-50" />
          <span className="font-mono">{call.name}</span>
          <span className="text-black/40 dark:text-white/40 truncate">({formatArgs(call.arguments)})</span>
          {call.status === "success" && call.output !== undefined && (
            <span className="text-black/50 dark:text-white/50">&rarr; {JSON.stringify(call.output)}</span>
          )}
          {call.status === "error" && call.error && <span className="text-red-500">&rarr; {call.error}</span>}
        </div>
      ))}
    </div>
  );
}
