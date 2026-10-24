// Service worker mínimo: permite instalar el portal como app en el celular.
// No guarda datos en caché: todo se consulta siempre al servidor (información personal y saldos al día).
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => {})
