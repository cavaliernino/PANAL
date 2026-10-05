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

const VERSION = "panal-v2";

const SHELL = [
  "./", "index.html", "national.html", "wui.html", "panal.js",
  "manifest.json", "icons/icon.svg", "icons/icon-192.png",
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

// How long to wait for the network before answering from the cache. Bad
// signal rarely fails fast — a request on one bar of signal can hang for a
// minute before the browser gives up, and the page sits on "Cargando…"
// with a perfectly good copy in hand. Past this, the copy is shown, with
// its age; the network request keeps going and refreshes the cache if it
// ever lands.
const NETWORK_TIMEOUT_MS = 6000;

// Anything answered from the cache says so, so the page can tell "offline"
// apart from "the server's data is old" — they call for different words.
async function fromCache(cache, url) {
  const hit = await cache.match(keyOf(url), { ignoreSearch: true });
  if (!hit) return null;
  const headers = new Headers(hit.headers);
  headers.set("X-Panal-Cache", "hit");
  return new Response(hit.body, { status: hit.status, statusText: hit.statusText, headers });
}

// "no-cache" makes the browser revalidate with the server every time — a
// 304 when nothing changed. Without it the HTTP cache may answer on its own
// heuristics, and right after a deploy a page could arrive stale while the
// data it reads is new.
async function networkFirst(event) {
  const url = event.request.url;
  const opening = caches.open(VERSION);
  const network = fetch(url, { cache: "no-cache" });
  // Registered before the first await, so the worker stays alive to store
  // a response that lands after the cache has already answered. The clone
  // is taken here, before the page can start reading the body.
  event.waitUntil(network.then(res => {
    if (!res.ok) return;
    const copy = res.clone();
    return opening.then(c => c.put(keyOf(url), copy));
  }).catch(() => {}));
  const cache = await opening;

  let timer;
  const slow = new Promise(resolve => { timer = setTimeout(resolve, NETWORK_TIMEOUT_MS); })
    .then(() => fromCache(cache, url));
  try {
    // Whichever answers first: the network, or the cache once the network
    // is too slow. A slow network with nothing cached still gets waited on.
    const first = await Promise.race([network, slow]);
    if (first) return first;
    return await network;
  } catch (err) {
    const hit = await fromCache(cache, url);
    if (hit) return hit;
    throw err;
  } finally {
    clearTimeout(timer);
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
    event.respondWith(networkFirst(event));
  } else if (CDN.includes(request.url)) {
    event.respondWith(cacheFirst(request));
  }
  // Anything else — basemap styles and tiles — goes straight to the network.
});
