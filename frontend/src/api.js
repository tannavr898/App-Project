const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 12000)
const RESPONSE_CACHE_PREFIX = "pulse-cache:"
const responseCache = new Map()

function getToken() {
  return localStorage.getItem("pulse-token")
}

export function saveAuth(username, token) {
  localStorage.setItem("pulse-token", token)
  localStorage.setItem("pulse-user", username)
}

export function clearAuth() {
  localStorage.removeItem("pulse-token")
  localStorage.removeItem("pulse-user")
}

export function getSavedUser() {
  return localStorage.getItem("pulse-user")
}

function trackApiMetric(eventName, payload) {
  if (typeof window === "undefined") return
  if (typeof window.gtag !== "function") return
  window.gtag("event", eventName, payload)
}

function getCacheStorageKey(cacheKey) {
  return `${RESPONSE_CACHE_PREFIX}${cacheKey}`
}

function readCachedResponse(cacheKey, cacheTtlMs) {
  const now = Date.now()
  const inMemory = responseCache.get(cacheKey)
  if (inMemory && now - inMemory.storedAt <= cacheTtlMs) {
    return new Response(inMemory.bodyText, {
      status: inMemory.status,
      statusText: inMemory.statusText,
      headers: inMemory.headers,
    })
  }

  if (typeof window === "undefined") return null

  const raw = window.localStorage.getItem(getCacheStorageKey(cacheKey))
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw)
    if (now - parsed.storedAt > cacheTtlMs) {
      window.localStorage.removeItem(getCacheStorageKey(cacheKey))
      return null
    }
    responseCache.set(cacheKey, parsed)
    return new Response(parsed.bodyText, {
      status: parsed.status,
      statusText: parsed.statusText,
      headers: parsed.headers,
    })
  } catch {
    window.localStorage.removeItem(getCacheStorageKey(cacheKey))
    return null
  }
}

function writeCachedResponse(cacheKey, response, bodyText) {
  const headers = {}
  response.headers.forEach((value, key) => {
    headers[key] = value
  })

  const cached = {
    bodyText,
    status: response.status,
    statusText: response.statusText,
    headers,
    storedAt: Date.now(),
  }

  responseCache.set(cacheKey, cached)

  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(getCacheStorageKey(cacheKey), JSON.stringify(cached))
  } catch {
    // Ignore storage quota / privacy failures.
  }
}

export function clearApiCache(match = null) {
  for (const key of [...responseCache.keys()]) {
    if (!match || match(key)) {
      responseCache.delete(key)
    }
  }

  if (typeof window === "undefined") return

  const keysToRemove = []
  for (let i = 0; i < window.localStorage.length; i += 1) {
    const key = window.localStorage.key(i)
    if (key && key.startsWith(RESPONSE_CACHE_PREFIX)) {
      const cacheKey = key.slice(RESPONSE_CACHE_PREFIX.length)
      if (!match || match(cacheKey)) {
        keysToRemove.push(key)
      }
    }
  }

  keysToRemove.forEach((key) => window.localStorage.removeItem(key))
}

// Authenticated fetch — automatically attaches the JWT header
export async function apiFetch(path, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, cacheKey = null, cacheTtlMs = 0, ...fetchOptions } = options
  const token = getToken()
  const method = (fetchOptions.method || "GET").toUpperCase()
  const isTaskPath = typeof path === "string" && path.startsWith("/tasks/")

  if (!isTaskPath && method === "GET" && cacheKey && cacheTtlMs > 0) {
    const cachedResponse = readCachedResponse(cacheKey, cacheTtlMs)
    if (cachedResponse) {
      trackApiMetric("api_request", {
        endpoint: path,
        method,
        status: cachedResponse.status,
        duration_ms: 0,
        cache_hit: true,
      })
      return cachedResponse
    }
  }

  const headers = {
    "Content-Type": "application/json",
    ...(isTaskPath ? { "Cache-Control": "no-store", Pragma: "no-cache" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers || {}),
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  const started = performance.now()

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...fetchOptions,
      ...(isTaskPath ? { cache: "no-store" } : {}),
      headers,
      signal: controller.signal,
    })
    const durationMs = Math.round(performance.now() - started)

    trackApiMetric("api_request", {
      endpoint: path,
      method: fetchOptions.method || "GET",
      status: res.status,
      duration_ms: durationMs,
    })

    if (res.status === 401) {
      clearAuth()
      window.location.reload()
    }

    if (!isTaskPath && method === "GET" && cacheKey && cacheTtlMs > 0 && res.ok) {
      const bodyText = await res.clone().text()
      writeCachedResponse(cacheKey, res, bodyText)
    }

    return res
  } catch (err) {
    const durationMs = Math.round(performance.now() - started)
    const reason = err?.name === "AbortError" ? "timeout" : "network"
    trackApiMetric("api_error", {
      endpoint: path,
      method: fetchOptions.method || "GET",
      reason,
      duration_ms: durationMs,
    })
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

// Auth calls (no token needed)
export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || "Login failed")
  return data
}
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/")
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

export async function registerPushSubscription(username) {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || typeof Notification === 'undefined') {
    throw new Error('Push reminders are not supported by this browser. Use Chrome or Edge on Android, or Safari 16.4+ on iOS.')
  }

  if (Notification.permission === 'denied') {
    throw new Error('Browser notifications are blocked. Enable them in your browser settings and refresh the page.')
  }

  if (Notification.permission === 'default') {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      throw new Error('Please allow browser notifications to enable reminders.')
    }
  }

  const keyRes = await apiFetch('/push/vapid_public_key')
  if (!keyRes.ok) {
    const err = await keyRes.text()
    throw new Error(err || 'Could not fetch public key.')
  }
  const { publicKey } = await keyRes.json()

  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  })

  const res = await apiFetch('/push/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, subscription: subscription.toJSON() }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Subscription failed')
  }
  return subscription
}
export async function register(username, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || "Registration failed")
  return data
}

export function getCachedJson(cacheKey, cacheTtlMs) {
  const response = readCachedResponse(cacheKey, cacheTtlMs)
  if (!response) return null

  try {
    return JSON.parse(response.bodyText)
  } catch {
    return null
  }
}