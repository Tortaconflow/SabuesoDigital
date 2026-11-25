/*
 * Sabueso Móvil — Service Worker
 * Guarda la app en el iPhone para que abra y funcione sin internet.
 * Solo cachea los archivos de la app; los datos de prospectos viven en IndexedDB del celular
 * y nunca pasan por este archivo ni por ningún servidor.
 */
const VERSION = "1.2.0";
const CACHE = `sabueso-movil-${VERSION}`;
const ARCHIVOS = [
    "./",
    "./index.html",
    "./app.css",
    "./app.js",
    "./motor.js",
    "./reglas/sabueso_reglas.json",
    "./manifest.webmanifest",
    "./icons/apple-touch-icon.png",
    "./icons/icon-192.png",
    "./icons/icon-512.png",
    "./icons/icon-maskable-512.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ARCHIVOS)));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k.startsWith("sabueso-movil-") && k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("message", (event) => {
    if (event.data === "activar-version-nueva") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    // Primero lo guardado (abre al instante y sin señal); en segundo plano se actualiza si hay internet.
    event.respondWith(
        caches.open(CACHE).then(async (cache) => {
            const guardado = await cache.match(req, { ignoreSearch: true }) ||
                (req.mode === "navigate" ? await cache.match("./index.html") : undefined);
            const red = fetch(req)
                .then((resp) => {
                    if (resp && resp.ok && resp.type === "basic") cache.put(req, resp.clone());
                    return resp;
                })
                .catch(() => undefined);
            if (guardado) {
                event.waitUntil(red);
                return guardado;
            }
            const resp = await red;
            return resp || new Response("Sin conexión y sin copia guardada de este archivo.", {
                status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" }
            });
        })
    );
});
