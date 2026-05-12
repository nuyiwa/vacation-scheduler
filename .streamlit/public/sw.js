// 방학 스케줄링 시스템 - Service Worker
// PWA 오프라인 지원 및 캐싱

const CACHE_NAME = 'vacation-scheduler-v1';
const STATIC_ASSETS = [
  '/',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

// 설치 시 정적 에셋 캐싱
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// 활성화 시 이전 캐시 정리
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// 네트워크 요청 가로채기 (Network First 전략)
self.addEventListener('fetch', (event) => {
  // Streamlit 관련 요청은 네트워크 우선
  if (event.request.url.includes('_stcore') || 
      event.request.url.includes('streamlit') ||
      event.request.url.includes('api') ||
      event.request.method !== 'GET') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request);
      })
    );
    return;
  }

  // 정적 에셋은 캐시 우선
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).then((response) => {
        // 유효한 응답만 캐싱
        if (response && response.status === 200 && response.type === 'basic') {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      }).catch(() => {
        // 완전 오프라인일 때 캐시된 페이지 반환
        return caches.match('/');
      });
    })
  );
});