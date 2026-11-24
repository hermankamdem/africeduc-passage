{% verbatim %}
const CACHE = "passage-v1";
const PAGE = "/agent/scan/";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname !== PAGE) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        // On ne garde en cache que la vraie page (jamais une redirection vers la connexion).
        if (r.ok && !r.redirected) {
          const copie = r.clone();
          caches.open(CACHE).then((c) => c.put(PAGE, copie));
        }
        return r;
      })
      .catch(() => caches.match(PAGE))
  );
});
{% endverbatim %}