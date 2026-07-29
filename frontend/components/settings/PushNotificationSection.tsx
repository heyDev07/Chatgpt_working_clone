"use client";

import { Bell, BellOff } from "lucide-react";
import { useEffect, useState } from "react";

import {
  disablePushNotifications,
  enablePushNotifications,
  getPushSubscriptionState,
  isPushSupported,
} from "@/lib/push";

export function PushNotificationSection() {
  const [state, setState] = useState<"loading" | "unsupported" | "denied" | "subscribed" | "unsubscribed">(
    "loading"
  );
  const [isToggling, setIsToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPushSubscriptionState().then(setState);
  }, []);

  const handleEnable = async () => {
    setIsToggling(true);
    setError(null);
    try {
      await enablePushNotifications();
      setState("subscribed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't enable notifications");
      setState(await getPushSubscriptionState());
    } finally {
      setIsToggling(false);
    }
  };

  const handleDisable = async () => {
    setIsToggling(true);
    try {
      await disablePushNotifications();
      setState("unsubscribed");
    } finally {
      setIsToggling(false);
    }
  };

  if (state === "loading" || state === "unsupported") return null;
  if (!isPushSupported()) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-black/10 dark:border-white/15 p-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-black/60 dark:text-white/60">
        <Bell size={13} />
        Push notifications
      </span>
      {state === "denied" ? (
        <p className="text-xs text-black/40 dark:text-white/40">
          Notifications are blocked for this site in your browser settings - re-enable them there to use this.
        </p>
      ) : state === "subscribed" ? (
        <>
          <p className="text-xs text-black/40 dark:text-white/40">
            Reminders will show up as a notification even when this tab isn&apos;t open.
          </p>
          <button
            onClick={handleDisable}
            disabled={isToggling}
            className="flex items-center gap-1.5 self-start rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10 disabled:opacity-50"
          >
            <BellOff size={13} />
            Turn off
          </button>
        </>
      ) : (
        <>
          <p className="text-xs text-black/40 dark:text-white/40">
            Get a real notification when a reminder fires, even if this tab isn&apos;t open.
          </p>
          <button
            onClick={handleEnable}
            disabled={isToggling}
            className="self-start rounded-lg bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black disabled:opacity-50"
          >
            {isToggling ? "Enabling..." : "Enable notifications"}
          </button>
        </>
      )}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
