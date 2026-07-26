"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Tooltip } from "@/components/ui/Tooltip";
import { deleteReminder, listReminders } from "@/lib/api/reminders";

// Polling, not push - there's no websocket/SSE channel for "something happened server-side with
// no request in flight" anywhere else in this app either, and a reminder firing is exactly that
// kind of event (the whole point of app/core/scheduler.py is that it runs independent of any
// request). 20s balances promptness against constant background traffic for what's fundamentally
// a personal-scale feature, not a chat message needing sub-second delivery.
const POLL_INTERVAL_MS = 20_000;

export function ReminderBell() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const seenIdsRef = useRef<Set<string>>(new Set());

  const { data: dueReminders = [] } = useQuery({
    queryKey: ["reminders", "due"],
    queryFn: () => listReminders(true),
    refetchInterval: POLL_INTERVAL_MS,
  });

  // Auto-opens the panel the moment a reminder neither this component nor the user has seen
  // yet shows up in a poll - the closest thing to a toast notification without building a
  // separate toast/portal system for what's otherwise just this one panel's own data.
  useEffect(() => {
    const currentIds = new Set(dueReminders.map((r) => r.id));
    const hasNewReminder = dueReminders.some((r) => !seenIdsRef.current.has(r.id));
    if (hasNewReminder && seenIdsRef.current.size > 0) {
      setIsOpen(true);
    } else if (seenIdsRef.current.size === 0 && currentIds.size > 0) {
      // First poll after mount already found due reminders (e.g. page was closed when one
      // fired) - still worth surfacing, just without the "just now" framing a mid-session
      // arrival gets.
      setIsOpen(true);
    }
    seenIdsRef.current = currentIds;
  }, [dueReminders]);

  const dismiss = async (id: string) => {
    await deleteReminder(id);
    seenIdsRef.current.delete(id);
    queryClient.invalidateQueries({ queryKey: ["reminders", "due"] });
  };

  return (
    <div className="relative">
      <Tooltip label="Reminders" side="bottom">
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          aria-label="Reminders"
          className="relative flex-shrink-0 rounded-lg p-2 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
        >
          <Bell size={16} />
          {dueReminders.length > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-medium text-white">
              {dueReminders.length}
            </span>
          )}
        </button>
      </Tooltip>
      {isOpen && (
        <>
          {/* Click-outside-to-close backdrop, same pattern as other dropdown/panel overlays in
              this app - invisible, just catches the outside click. */}
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-black/10 bg-white p-2 shadow-lg dark:border-white/10 dark:bg-neutral-800">
            <div className="px-2 py-1.5 text-sm font-medium text-black/70 dark:text-white/70">Reminders</div>
            {dueReminders.length === 0 ? (
              <p className="px-2 py-3 text-sm text-black/40 dark:text-white/40">Nothing due right now</p>
            ) : (
              <div className="flex flex-col gap-1">
                {dueReminders.map((reminder) => (
                  <div
                    key={reminder.id}
                    className="flex items-start gap-2 rounded-lg px-2 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10"
                  >
                    <Bell size={14} className="mt-0.5 flex-shrink-0 text-blue-500" />
                    <span className="flex-1 text-black/80 dark:text-white/80">{reminder.message}</span>
                    <button
                      onClick={() => dismiss(reminder.id)}
                      aria-label="Dismiss reminder"
                      className="flex-shrink-0 text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
