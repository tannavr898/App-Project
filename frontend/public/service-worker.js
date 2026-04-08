self.addEventListener('push', event => {
  const payload = event.data?.json() || {}
  const title = payload.title || 'Pulse Reminder'
  const options = {
    body: payload.body || 'Open Pulse to check your progress.',
    data: {
      url: payload.url || '/',
    },
    badge: '/favicon.ico',
    icon: '/favicon.ico',
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', event => {
  const url = event.notification.data?.url || '/'
  event.notification.close()
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url === url || client.url.endsWith(url)) {
          return client.focus()
        }
      }
      return clients.openWindow(url)
    })
  )
})
