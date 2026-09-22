/** Session cookie auth helpers (D17). Always send credentials for API calls. */

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: 'include',
    headers: init?.headers,
  })
}

export async function fetchAuthMe(): Promise<{ authenticated: boolean; username: string | null }> {
  const response = await apiFetch('/api/auth/me')
  if (!response.ok) {
    return { authenticated: false, username: null }
  }
  const body = (await response.json()) as { authenticated?: boolean; username?: string | null }
  return {
    authenticated: Boolean(body.authenticated),
    username: body.username ?? null,
  }
}

export async function login(username: string, password: string): Promise<void> {
  const response = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    let message = 'Неверный логин или пароль'
    try {
      const body = (await response.json()) as { error?: { message?: string } }
      message = body.error?.message ?? message
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
}

export async function logout(): Promise<void> {
  await apiFetch('/api/auth/logout', { method: 'POST' })
}
