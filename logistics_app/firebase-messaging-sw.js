importScripts('https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.22.0/firebase-messaging-compat.js');

const firebaseConfig = {
  apiKey: "AIzaSyDb0KuNTbWvtyqASC4bM44UMw4hQtSU-Ss",
  authDomain: "rotra-aeb0c.firebaseapp.com",
  projectId: "rotra-aeb0c",
  storageBucket: "rotra-aeb0c.firebasestorage.app",
  messagingSenderId: "519697196364",
  appId: "1:519697196364:web:4d4575b7ee02adbf6f1be9",
  measurementId: "G-VCDHP403Z7"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

console.log('🔥 Firebase Messaging Service Worker loaded');

// Background message handler
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received background message:', payload);
    
    const notificationTitle = payload.notification?.title || 'Rotra Logistics';
    const notificationOptions = {
        body: payload.notification?.body || 'You have a new notification',
        icon: '/static/images/logo.png',
        badge: '/static/images/badge.png',
        data: payload.data || {},
        tag: payload.data?.type || 'general',
        requireInteraction: true
    };

    // Show notification
    return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Notification click handler
self.addEventListener('notificationclick', function(event) {
    console.log('🔔 Notification click received:', event.notification.tag);
    
    event.notification.close();
    
    const urlToOpen = '/trip-management/';

    event.waitUntil(
        clients.matchAll({type: 'window'}).then(function(windowClients) {
            // Check if there's already a window/tab open with the target URL
            for (let client of windowClients) {
                if (client.url.includes(urlToOpen) && 'focus' in client) {
                    return client.focus();
                }
            }
            
            // If no window is open, open a new one
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

// Service worker installation
self.addEventListener('install', function(event) {
    console.log('✅ Service worker installed');
    self.skipWaiting();
});

// Service worker activation
self.addEventListener('activate', function(event) {
    console.log('✅ Service worker activated');
    return self.clients.claim();
});