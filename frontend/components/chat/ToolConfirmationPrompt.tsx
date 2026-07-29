"use client";

import { AlertTriangle } from "lucide-react";

import type { ToolConfirmationEventData } from "@/lib/api/stream";

// Human-readable summary per restricted tool - matches the spirit of ToolActivityList's
// describeActivity (human phrasing over raw tool_name/JSON.stringify(arguments)), but framed as
// "about to happen" rather than past/present tense, since this is a decision prompt, not a log.
function describeAction(call: ToolConfirmationEventData): string {
  const args = call.arguments;
  switch (call.name) {
    case "send_gmail":
      return `Send an email to ${args.to} with subject "${args.subject}"?`;
    case "create_calendar_event":
      return `Create a calendar event "${args.summary}"${args.start_iso ? ` at ${args.start_iso}` : ""}?`;
    default:
      return `Run ${call.name.replace(/_/g, " ")}?`;
  }
}

export function ToolConfirmationPrompt({
  call,
  isResolving,
  onApprove,
  onReject,
}: {
  call: ToolConfirmationEventData;
  isResolving: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="mx-auto max-w-3xl w-full px-4 pb-2">
      <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
        <AlertTriangle size={16} className="mt-0.5 flex-shrink-0 text-amber-600 dark:text-amber-500" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-black/80 dark:text-white/80">{describeAction(call)}</p>
          {call.name === "send_gmail" && typeof call.arguments.body === "string" && (
            <p className="mt-1 whitespace-pre-line text-xs text-black/50 dark:text-white/50 line-clamp-3">
              {call.arguments.body}
            </p>
          )}
          <div className="mt-2 flex gap-2">
            <button
              onClick={onApprove}
              disabled={isResolving}
              className="rounded-lg bg-black dark:bg-white px-3 py-1.5 text-xs font-medium text-white dark:text-black disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={onReject}
              disabled={isResolving}
              className="rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
