// Minimal Web Push service worker - its only job is turning a push event (sent by
// backend/app/services/push_service.py when a reminder fires) into a real OS notification, which
// is the one thing that works even when no tab for this app is open. Registered once from
// lib/push.ts; not a general offline/caching service worker, deliberately - this app has no
// offline-first requirement, so there's nothing to gain from intercepting fetch() here too.

self.addEventListener("push", (event) => {
  let payload = { title: "Reminder", body: "" };
  try {
    payload = event.data.json();
  } catch {
    // Non-JSON or empty payload - fall back to the default above rather than throwing, since a
    // malformed push should still surface *something* rather than silently disappearing.
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "Reminder", {
      body: payload.body || "",
      icon: "/next.svg",
    })
  );
});

// Clicking the notification focuses an existing tab if one's open, otherwise opens a new one -
// without this, clicking the OS notification does nothing at all in most browsers.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) return client.focus();
      }
      return self.clients.openWindow("/chat");
    })
  );
});
