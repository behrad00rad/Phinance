function cookie(name) { return document.cookie.split('; ').find(row => row.startsWith(name + '='))?.split('=')[1] }
export async function api(path, options = {}) {
  const response = await fetch('/api/' + path, { credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(cookie('csrftoken') || '') }, ...options })
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || Object.values(data).flat().join(' ') || 'خطایی رخ داد') }
  return response.json()
}
export const write = (path, data, method = 'POST') => api(path, { method, body: JSON.stringify(data) })
