self.addEventListener('push', function(event) {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch(e) {
            data = {body: event.data.text()};
        }
    }
    
    const title = data.title || "Toplantı Hatırlatması";
    const options = {
        body: data.body || "Yaklaşan bir toplantınız var.",
        icon: '/static/icon-192x192.png',
        badge: '/static/icon-192x192.png',
        vibrate: [200, 100, 200, 100, 200, 100, 200],
        data: {
            url: data.url || '/dashboard'
        }
    };
    
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(event.notification.data.url);
            }
        })
    );
});
