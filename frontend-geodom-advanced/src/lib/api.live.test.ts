// @vitest-environment jsdom
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest'

beforeEach(() => {
  vi.resetModules()
  vi.stubEnv('VITE_API_URL','http://localhost:8000/api/v1')
  vi.stubEnv('VITE_API_REQUEST_TIMEOUT_MS','1000')
  sessionStorage.clear(); localStorage.clear()
})
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks() })
const json=(value:unknown,status=200) => new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}})

describe('live cookie session',() => {
  it('restores from /me without a browser-stored token and sends credentials',async () => {
    sessionStorage.setItem('geodom-session-v1',JSON.stringify({user:{id:'old'},token:'obsolete'}))
    const fetch=vi.fn().mockResolvedValue(json({id:42,login:'ivan'})); vi.stubGlobal('fetch',fetch)
    const {api}=await import('./api')
    await expect(api.currentUser()).resolves.toEqual({id:'42',login:'ivan'})
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/me',expect.objectContaining({credentials:'include'}))
    expect(new Headers(fetch.mock.calls[0][1].headers).has('Authorization')).toBe(false)
    expect(api.session()).toBeNull()
  })
  it('does not turn a network outage into a successful login',async () => {
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('offline')))
    const {api}=await import('./api')
    await expect(api.currentUser()).rejects.toThrow('Не удалось связаться')
  })
  it('treats rejected cookies as anonymous',async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json({detail:'unauthorized'},401)))
    const {api}=await import('./api'); await expect(api.currentUser()).resolves.toBeNull()
  })
  it('uses the user envelope and logs out on the server',async () => {
    const fetch=vi.fn().mockResolvedValueOnce(json({user:{id:5,login:'test'}})).mockResolvedValueOnce(new Response(null,{status:204}))
    vi.stubGlobal('fetch',fetch)
    const {api}=await import('./api')
    await expect(api.login('test','password')).resolves.toEqual({id:'5',login:'test'})
    expect(sessionStorage.length).toBe(0)
    await api.logout()
    expect(fetch.mock.calls[1][0]).toBe('http://localhost:8000/api/v1/auth/logout')
    expect(fetch.mock.calls[1][1].method).toBe('POST')
  })
  it('uses multipart upload without a JSON content type',async () => {
    const fetch=vi.fn().mockResolvedValue(json({id:1}));vi.stubGlobal('fetch',fetch)
    const {api}=await import('./api'); await api.upload('5',new File(['photo'],'photo.png',{type:'image/png'}))
    expect(fetch.mock.calls[0][1].body).toBeInstanceOf(FormData)
    expect(new Headers(fetch.mock.calls[0][1].headers).has('Content-Type')).toBe(false)
  })
  it('does not request unsupported live endpoints',async () => {
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
    const {api}=await import('./api')
    await api.proStatus();await api.demandProfile()
    await api.event({request_id:'r',event:'click',entity_type:'apartment',entity_id:1,position:1})
    expect(fetch).not.toHaveBeenCalled()
  })
})

it('loads real map objects from the supported endpoint',async () => {
  const fetch=vi.fn().mockResolvedValue(json([{osm_id:123,category:'education',subcategory:'school',name:'Школа',lat:56,lon:92}]))
  vi.stubGlobal('fetch',fetch)
  const {api}=await import('./api')
  const rows=await api.geoObjects()
  expect(rows[0]).toMatchObject({name:'Школа',lat:56,lon:92})
  expect(fetch.mock.calls[0][0]).toBe('http://localhost:8000/api/v1/geo-objects')
})
