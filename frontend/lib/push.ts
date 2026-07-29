import { getVapidPublicKey, registerPushSubscription, unregisterPushSubscription } from "@/lib/api/push";

// pushManager.subscribe() needs the VAPID public key as a Uint8Array, not the base64url string
// the backend hands out - browsers don't do this conversion themselves.
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

export function isPushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window;
}

export async function getPushSubscriptionState(): Promise<"unsupported" | "denied" | "subscribed" | "unsubscribed"> {
  if (!isPushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  const registration = await navigator.serviceWorker.getRegistration("/sw.js");
  const existing = await registration?.pushManager.getSubscription();
  return existing ? "subscribed" : "unsubscribed";
}

// Registers the service worker (idempotent - browsers no-op a re-register of the same script),
// requests permission if not already granted/denied, subscribes with the backend's VAPID public
// key, then tells the backend about the subscription so push_service.py has somewhere to send to.
export async function enablePushNotifications(): Promise<void> {
  if (!isPushSupported()) throw new Error("Push notifications aren't supported in this browser");

  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notification permission was not granted");

  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  const { public_key } = await getVapidPublicKey();
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    // lib.dom's PushSubscriptionOptionsInit wants ArrayBuffer-backed BufferSource specifically,
    // not the wider ArrayBufferLike a Uint8Array's type parameter defaults to - the value itself
    // is already a real ArrayBuffer at runtime (Uint8Array.from never allocates a
    // SharedArrayBuffer), this is purely satisfying the stricter generic.
    applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
  });

  await registerPushSubscription(subscription.toJSON() as PushSubscriptionJSON);
}

export async function disablePushNotifications(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration("/sw.js");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return;
  await unregisterPushSubscription(subscription.endpoint);
  await subscription.unsubscribe();
}
