"use client";

import { Check, Loader2, Wrench, X } from "lucide-react";

import type { ToolActivity } from "@/lib/types";

// Human-readable label per tool, matching how ChatGPT/Claude describe tool use ("Searched the
// web for X") instead of a raw function name - the previous version showed the literal tool
// name plus JSON.stringify(arguments)/JSON.stringify(output) inline, which dumped an entire
// Tavily search result blob (or a Playwright page snapshot) as one long unreadable line.
function describeActivity(call: ToolActivity): string {
  const args = call.arguments;
  switch (call.name) {
    case "tavily_search":
    case "tavily_research":
      return args.query ? `Searching the web for "${args.query}"` : "Searching the web";
    case "tavily_extract":
    case "tavily_crawl":
    case "tavily_map":
      return args.url ? `Reading ${args.url}` : "Reading a web page";
    case "calculator":
      return args.expression ? `Calculating ${args.expression}` : "Calculating";
    case "sql_query":
      return "Querying the database";
    case "generate_image":
      return args.prompt ? `Generating an image of "${args.prompt}"` : "Generating an image";
    case "browser_navigate":
      return args.url ? `Browsing to ${args.url}` : "Navigating";
    case "search_gmail":
      return args.query ? `Searching Gmail for "${args.query}"` : "Searching Gmail";
    case "list_calendar_events":
      return "Checking your calendar";
    case "send_gmail":
      return args.to ? `Sending email to ${args.to}` : "Sending email";
    case "create_calendar_event":
      return args.summary ? `Creating calendar event "${args.summary}"` : "Creating calendar event";
    default:
      if (call.name.startsWith("browser_")) return "Using the browser";
      // Fallback for anything not explicitly mapped: prettify the raw tool_name.
      return call.name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  }
}

function pastTense(label: string): string {
  // "Searching the web for X" -> "Searched the web for X" once the call succeeds - cheap
  // heuristic (this app's own tool set has a small, known list of -ing verbs), not general NLP.
  return label.replace(/^(\w+)ing\b/, (_match, stem: string) => {
    if (stem === "Search") return "Searched";
    if (stem === "Read") return "Read";
    if (stem === "Calculat") return "Calculated";
    if (stem === "Generat") return "Generated";
    if (stem === "Browsing") return "Browsed";
    if (stem === "Us") return "Used";
    if (stem === "Query" || stem === "Querying") return "Queried";
    if (stem === "Send") return "Sent";
    return `${stem}ed`;
  });
}

export function ToolActivityList({ activity }: { activity: ToolActivity[] }) {
  if (activity.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      {activity.map((call) => {
        const label = describeActivity(call);
        return (
          <div
            key={call.id}
            className="flex items-center gap-2 rounded-lg border border-black/10 dark:border-white/10 px-3 py-1.5 text-xs text-black/60 dark:text-white/60 w-fit max-w-full"
          >
            {call.status === "calling" && <Loader2 size={13} className="flex-shrink-0 animate-spin" />}
            {call.status === "success" && (
              <Check size={13} className="flex-shrink-0 text-green-600 dark:text-green-500" />
            )}
            {call.status === "error" && <X size={13} className="flex-shrink-0 text-red-500" />}
            {call.status === "calling" ? (
              <Wrench size={13} className="flex-shrink-0 opacity-50" />
            ) : null}
            <span className="truncate">
              {call.status === "success" ? pastTense(label) : label}
              {call.status === "error" && call.error ? (
                <span className="text-red-500"> — {call.error.slice(0, 80)}</span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}
