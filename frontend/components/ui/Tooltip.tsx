"use client";

import type { ReactNode } from "react";

// CSS-only (group-hover), not a JS-positioned/portaled tooltip library - every place this
// wraps a button is a small, fixed-position icon in a toolbar, so there's no viewport-edge
// collision risk that would need real positioning logic. Matches the small dark pill ChatGPT
// shows on icon-only buttons (e.g. the mic button's "Dictate"), which aria-label alone doesn't
// give you - aria-label is read by screen readers but produces no visible on-hover affordance.
export function Tooltip({
  label,
  children,
  side = "top",
}: {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
}) {
  return (
    <span className="relative inline-flex group/tooltip">
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-neutral-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity delay-300 group-hover/tooltip:opacity-100 dark:bg-neutral-700 ${
          side === "top" ? "bottom-full mb-2" : "top-full mt-2"
        }`}
      >
        {label}
      </span>
    </span>
  );
}
