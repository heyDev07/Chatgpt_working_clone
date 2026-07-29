import { apiFetch } from "@/lib/api/client";

export function getVapidPublicKey(): Promise<{ public_key: string }> {
  return apiFetch<{ public_key: string }>("/push/vapid-public-key");
}

export function registerPushSubscription(subscription: PushSubscriptionJSON): Promise<{ subscribed: boolean }> {
  return apiFetch<{ subscribed: boolean }>("/push", {
    method: "POST",
    body: JSON.stringify(subscription),
  });
}

export function unregisterPushSubscription(endpoint: string): Promise<void> {
  return apiFetch<void>("/push/unsubscribe", {
    method: "POST",
    body: JSON.stringify({ endpoint }),
  });
}
