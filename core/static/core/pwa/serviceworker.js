// serviceworker.js

// V7: Corregida la intercepción de la API
const CACHE_NAME = 'pedidos-lges-v7'; // ¡Importante! Nuevo nombre de caché.
const OFFLINE_URL = '/offline/'; // La URL de nuestra página offline.

// We will only cache the absolutely essential, local URLs during installation.
const urlsToCache = [
    '/',
    OFFLINE_URL
];

// 'install' event: Caches the essential base files.
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Cache opened, adding essential URLs for v5');
            return cache.addAll(urlsToCache);
        }).catch(error => {
            console.error('Failed to cache essential URLs during install:', error);
        })
    );
});

// 'activate' event: Cleans up old caches.
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Cleaning up old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// 'fetch' event: Intercepts network requests.
self.addEventListener('fetch', event => {
    const requestUrl = new URL(event.request.url);


    if (requestUrl.pathname.includes('/pdf/') || requestUrl.pathname.endsWith('.pdf')) {
        return; // Al no llamar a event.respondWith, el navegador gestiona la descarga.
    }

    if (requestUrl.pathname.includes('/api/')) {
        event.respondWith(fetch(event.request));
        return; // Detiene la ejecución aquí para las peticiones de la API
    }
    


    // Handle navigation requests (HTML pages)
    if (event.request.mode === 'navigate') {
        event.respondWith((async () => {
            try {
                const networkResponse = await fetch(event.request);
                const cache = await caches.open(CACHE_NAME);
                cache.put(event.request, networkResponse.clone());
                return networkResponse;
            } catch (error) {
                console.log('Network request failed for navigation. Trying cache.', error);
                const cache = await caches.open(CACHE_NAME);
                const cachedResponse = await cache.match(event.request);
                return cachedResponse || await cache.match(OFFLINE_URL);
            }
        })());
        return;
    }

    // Handle non-navigation requests (CSS, JS, images, etc.) with a Cache-First strategy
    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(event.request);

        if (cachedResponse) {
            return cachedResponse;
        }

        try {
            const networkResponse = await fetch(event.request);
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
        } catch (error) {
            console.log('Failed to fetch non-navigation resource from network:', event.request.url);
        }
    })());
});