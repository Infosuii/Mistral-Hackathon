export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) throw new Error(`HTTP ${response.status} on ${path}`)
  return response.json()
}

export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: 'POST',
    signal: AbortSignal.timeout(60_000),
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function audioSource(url: string) {
  return url.startsWith('/audio/') ? `/api${url}` : url
}
