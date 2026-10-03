/* PANAL service worker.
 *
 * What it is for: the app opens on a phone with bad signal, and shows the
 * last data it had — with its age, which every page states. What it must
 * never do is make old data look current, so data is always fetched from
 * the network first and the cache is only the fallback.
 *
 *   - our pages, scripts and data: network first, cache if offline
 *   - pinned CDN libraries: cache first (a versioned URL never changes)
 *   - map tiles and anything else: not touched
 *
 * Bump VERSION when the shell changes shape; old caches are dropped.
 */

const VERSION = "panal-v1";

const SHELL = [
  "./", "index.html", "national.html", "wui.html", "panal.js",
  "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png",
];

const CDN = [
  "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.6.1/maplibre-gl.js",
  "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.6.1/maplibre-gl.css",
  "https://cdn.jsdelivr.net/npm/h3-js@4.2.1/dist/h3-js.umd.js",
  "https://cdn.jsdelivr.net/npm/deck.gl@9.1.14/dist.min.js",
];

self.addEventListener("install", event => {
  event.waitUntil(
    // "reload": straight from the server, so a stale HTTP-cached copy never
    // becomes the offline fallback.
    caches.open(VERSION)
      .then(c => c.addAll([...SHELL, ...CDN].map(u => new Request(u, { cache: "reload" }))))
      .then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION)
                                    .map(k => caches.delete(k))))
      .then(() => self.clients.claim()));
});

// Data URLs carry a cache-busting query (?t=…). Stored under the bare URL,
// or every refresh would add an entry that is never read again.
const keyOf = url => {
  const u = new URL(url);
  if (u.pathname.includes("/data/")) u.search = "";
  return u.href;
};

// "no-cache" makes the browser revalidate with the server every time — a
// 304 when nothing changed. Without it the HTTP cache may answer on its own
// heuristics, and right after a deploy a page could arrive stale while the
// data it reads is new.
async function networkFirst(request) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(request.url, { cache: "no-cache" });
    if (res.ok) cache.put(keyOf(request.url), res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(keyOf(request.url), { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(request.url);
  if (hit) return hit;
  const res = await fetch(request.url, { mode: "cors" });
  if (res.ok) cache.put(request.url, res.clone());
  return res;
}

self.addEventListener("fetch", event => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  if (url.origin === self.location.origin) {
    event.respondWith(networkFirst(request));
  } else if (CDN.includes(request.url)) {
    event.respondWith(cacheFirst(request));
  }
  // Anything else — basemap styles and tiles — goes straight to the network.
});
