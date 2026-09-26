const CACHE_NAME = 'nishiyama-v4';
const APP_SHELL = ['/home', '/static/app.css', '/static/brand.css', '/static/home.css', '/static/splash.css', '/static/final-spec.css', '/static/ver2.css', '/static/home-v21.css', '/static/clue.css', '/static/difficulty.css', '/static/splash-final.css', '/static/img/home-tsutsuji.jpg', '/static/img/logo.png', '/static/app.js', '/static/manifest.json'];
// 初回表示に必要なファイルを先に保存し、通信できない場合もホームを返します。
self.addEventListener('install', (event) => { event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))); self.skipWaiting(); });
self.addEventListener('activate', (event) => { event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith('nishiyama-') && key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim())); });
// キャッシュ優先で再訪を高速化し、未保存のリソースは取得後にキャッシュします。
self.addEventListener('fetch', (event) => { event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => { const copy = response.clone(); caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)); return response; }).catch(() => caches.match('/home')))); });
