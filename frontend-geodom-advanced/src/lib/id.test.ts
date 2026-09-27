import { describe,expect,it,vi } from 'vitest'
import { createId,demoPasswordDigest,matchesDemoPassword } from './id'

describe('browser-safe ids',() => {
  it('returns an id when randomUUID is unavailable',() => {
    const original = globalThis.crypto
    Object.defineProperty(globalThis,'crypto',{
      configurable:true,
      value:{ getRandomValues:(bytes:Uint8Array) => { bytes.fill(7); return bytes } }
    })
    try {
      expect(createId()).toMatch(/^[a-f0-9-]{36}$/)
    } finally {
      Object.defineProperty(globalThis,'crypto',{ configurable:true,value:original })
    }
  })

  it('returns an id even when Web Crypto is unavailable',() => {
    const original = globalThis.crypto
    Object.defineProperty(globalThis,'crypto',{ configurable:true,value:undefined })
    const random = vi.spyOn(Math,'random').mockReturnValue(.42)
    try {
      expect(createId()).toMatch(/^demo-/)
    } finally {
      random.mockRestore()
      Object.defineProperty(globalThis,'crypto',{ configurable:true,value:original })
    }
  })

  it('uses a deterministic demo password digest without secure-context APIs',async () => {
    const digest=demoPasswordDigest('secret123')
    expect(digest).toMatch(/^demo-fnv1a:/)
    expect(await matchesDemoPassword('secret123',digest)).toBe(true)
    expect(await matchesDemoPassword('wrong',digest)).toBe(false)
  })
})
