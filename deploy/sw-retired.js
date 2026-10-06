/* The service worker that retires panal.ninobozzi.cl.
 *
 * PANAL moved to https://panalforestal.cl on 2026-10-06. nginx answers every
 * URL of the old name with a 301, except /sw.js, which serves this file —
 * see deploy/nginx/panalforestal.cl.conf for why.
 *
 * A phone that installed the app under the old name still runs the old
 * web/sw.js, and it would keep answering from its cache forever: every
 * request it makes is redirected to another origin and fails. The next time
 * the app opens, the browser looks for a new sw.js and gets this one, which
 * takes over at once, drops the caches, sends each open window to the same
 * page on the new name, and unregisters itself.
 *
 * No fetch handler on purpose: while it lives, everything goes to the
 * network, where the 301 is.
 */

const NEW_ORIGIN = "https://panalforestal.cl";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
    await self.clients.claim();
    const windows = await self.clients.matchAll({ type: "window" });
    // A browser that cannot navigate a client still ends up there: with the
    // worker gone, the next open hits the 301.
    await Promise.all(windows.map(w => {
      const u = new URL(w.url);
      return w.navigate(NEW_ORIGIN + u.pathname + u.search + u.hash).catch(() => {});
    }));
    await self.registration.unregister();
  })());
});
