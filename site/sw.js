/* Boss Cigar — service worker: funciona sem rede (ex.: dentro de uma tabacaria).
   Páginas e dados: rede primeiro, cache como recurso. Bibliotecas e mosaicos do mapa: cache primeiro. */
const VERSION = "bc-v1";
const SHELL = ["./", "index.html", "aficionado.js", "manifest.webmanifest", "icon-192.png",
  "data/cigars.json", "data/meta.json", "data/quality.json", "data/brands.json", "data/tobacco.json",
  "data/shops.json", "data/fr_catalog.json", "data/prices.json", "data/home.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => Promise.allSettled(SHELL.map(u => c.add(u)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === location.origin;
  if (sameOrigin) {
    e.respondWith(fetch(req).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put(req, copy)); return r; })
      .catch(() => caches.match(req, { ignoreSearch: true }).then(r => r || caches.match("index.html"))));
  } else if (/unpkg\.com|tile\.openstreetmap\.org/.test(url.host)) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(resp => { const copy = resp.clone(); caches.open(VERSION).then(c => c.put(req, copy)); return resp; })));
  }
});
