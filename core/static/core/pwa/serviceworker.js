// V5: A more resilient installation strategy.
const CACHE_NAME = 'louis-ferry-cache-v5'; // ¡Importante! Nuevo nombre de caché.
const OFFLINE_URL = '/offline/'; // La URL de nuestra página offline.

// We will only cache the absolutely essential, local URLs during installation.
// Other assets (like CDN files) will be cached on the first visit via the 'fetch' event handler.
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

// 'fetch' event: Intercepts network requests. Using async/await.
self.addEventListener('fetch', event => {
    // Handle navigation requests (HTML pages)
    if (event.request.mode === 'navigate') {
        event.respondWith((async () => {
            try {
                // 1. Try the network first.
                const networkResponse = await fetch(event.request);

                // 2. If successful, clone it, cache it, and return it.
                const cache = await caches.open(CACHE_NAME);
                cache.put(event.request, networkResponse.clone());
                return networkResponse;

            } catch (error) {
                // 3. If the network fails, try to serve from the cache.
                console.log('Network request failed for navigation. Trying cache.', error);
                const cache = await caches.open(CACHE_NAME);
                const cachedResponse = await cache.match(event.request);
                
                // If found in cache, return it. Otherwise, return the offline page.
                return cachedResponse || await cache.match(OFFLINE_URL);
            }
        })());
        return; // End execution for navigate requests
    }

    // Handle non-navigation requests (CSS, JS, images, etc.) with a Cache-First strategy
    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(event.request);

        // If the resource is in the cache, return it.
        if (cachedResponse) {
            return cachedResponse;
        }

        // If not, try to fetch it from the network.
        try {
            const networkResponse = await fetch(event.request);
            // If successful, cache the new resource for future offline use and return it.
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
        } catch (error) {
            // If fetching from network also fails, the resource is unavailable.
            console.log('Failed to fetch non-navigation resource from network:', event.request.url);
        }
    })());
});