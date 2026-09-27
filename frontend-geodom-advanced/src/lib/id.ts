let fallbackCounter = 0

function fallbackUuid() {
  fallbackCounter = (fallbackCounter + 1) % 0xffffff
  const time = Date.now().toString(16).padStart(12,'0')
  const random = Math.floor(Math.random()*0xffffffff).toString(16).padStart(8,'0')
  const counter = fallbackCounter.toString(16).padStart(6,'0')
  return `demo-${time}-${random}-${counter}`
}

export function createId():string {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID()

  if (typeof cryptoApi?.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    cryptoApi.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes,byte => byte.toString(16).padStart(2,'0')).join('')
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
  }

  return fallbackUuid()
}

function fnv1a(value:string) {
  let hash = 0x811c9dc5
  for (let index=0;index<value.length;index++) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash,0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8,'0')
}

export function demoPasswordDigest(value:string) {
  return `demo-fnv1a:${fnv1a(value)}`
}

export async function matchesDemoPassword(value:string,storedDigest:string) {
  const fallback = demoPasswordDigest(value)
  if (storedDigest === fallback) return true

  // Backwards compatibility with demo accounts created before the
  // browser-safe digest was introduced.
  if (/^[a-f0-9]{64}$/i.test(storedDigest) && globalThis.crypto?.subtle) {
    try {
      const bytes = new TextEncoder().encode(value)
      const digest = await globalThis.crypto.subtle.digest('SHA-256',bytes)
      const legacy = Array.from(new Uint8Array(digest),byte => byte.toString(16).padStart(2,'0')).join('')
      return legacy === storedDigest
    } catch {
      return false
    }
  }

  return false
}
