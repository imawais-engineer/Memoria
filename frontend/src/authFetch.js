// Attaches the stored JWT to same-origin API requests as a Bearer token.
const AUTH_STORAGE_KEY = 'memoria_auth'

function storedToken() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || 'null')?.access_token || null
  } catch {
    return null
  }
}

function isSameOriginRequest(input) {
  const url = typeof input === 'string' ? input : input?.url || ''
  return url.startsWith('/') && !url.startsWith('//')
}

export function installAuthFetch() {
  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input, init = {}) => {
    const token = isSameOriginRequest(input) ? storedToken() : null
    if (!token) return originalFetch(input, init)

    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined))
    if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
    const res = await originalFetch(input, { ...init, headers })
    const url = typeof input === 'string' ? input : input.url
    if (res.status === 401 && !url.startsWith('/auth/login') && !url.startsWith('/auth/signup')) {
      // Token expired or invalid: drop the session and return to sign-in.
      localStorage.removeItem(AUTH_STORAGE_KEY)
      window.location.assign('/auth')
    }
    return res
  }
}
