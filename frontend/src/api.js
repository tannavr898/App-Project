const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

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

// Authenticated fetch — automatically attaches the JWT header
export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearAuth()
    window.location.reload()
  }
  return res
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