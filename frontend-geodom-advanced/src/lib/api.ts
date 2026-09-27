import { demoApartments } from '../data/demo'
import { demoGeoRows } from '../data/demoGeoObjects'
import { demoRecommend, logDemoEvent, rememberRecommendation } from './recommendations'
import { normalizeGeoObjects, type GeoObject } from './dataSanitizers'
import { buildDistrictStats, type DistrictStats } from './districtStats'
import type { SharedDemandProfile } from './demandProfile'
import type { LeadStage, ProLead } from './pro'
import { createId, demoPasswordDigest, matchesDemoPassword } from './id'
import { withLocalHousingMedia } from './media'
import { backendListingPayload, backendRecommendationPayload, mapBackendApartment, mapBackendDistrict, mapBackendPhoto, mapBackendRecommendation, mapBackendUser, type BackendApartment, type BackendDistrict, type BackendPage, type BackendPhoto, type BackendRecommendationResponse } from './backendAdapter'
import type { ApartmentPhoto, District, Apartment, InteractionPayload, ListingInput, RecommendationRequest, RecommendationResponse, User } from '../types'

const base = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const configuredTimeout=Number(import.meta.env.VITE_API_REQUEST_TIMEOUT_MS || 15000)
const requestTimeoutMs=Number.isFinite(configuredTimeout) && configuredTimeout >= 1000 ? configuredTimeout : 15000
export const isDemo = !base

export class ApiError extends Error {
  status:number|null
  constructor(message:string,status:number|null=null) {
    super(message)
    this.name='ApiError'
    this.status=status
  }
}
const homesKey = 'geodom-demo-apartments-v1'
const usersKey = 'geodom-demo-users-v1'
const sessionKey = 'geodom-session-v1'
const delay = () => new Promise(resolve => setTimeout(resolve, 180))

type ProAccountStatus = {
  user_id:number|string
  status:'none'|'trial'|'active'|'expired'|'disabled'
  trial_until?:string|null
}
function read<T>(key: string, fallback: T): T { try { return JSON.parse(localStorage.getItem(key) || '') as T } catch { return fallback } }
function loadDemandProfileForDemo():SharedDemandProfile|null {
  const value=read<SharedDemandProfile|null>('geodom-shared-demand-profile-v1',null)
  return value && typeof value.id==='string' ? value : null
}
function save(key: string, value: unknown) { localStorage.setItem(key, JSON.stringify(value)) }
// Live authentication is held only by the HttpOnly cookie. Demo sessions stay separate.
function getSession(): { user: User } | null {
  if (!isDemo) return null
  try { return JSON.parse(sessionStorage.getItem(sessionKey) || '') } catch { return null }
}
const storeSession = (session: { user: User } | null) => session ? sessionStorage.setItem(sessionKey, JSON.stringify(session)) : sessionStorage.removeItem(sessionKey)
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller=new AbortController()
  const timeout=globalThis.setTimeout(() => controller.abort(),requestTimeoutMs)
  let response:Response

  try {
    response=await fetch(`${base}${path}`,{
      ...options,
      credentials:'include',
      signal:options.signal ?? controller.signal,
      headers:{
        ...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}),
        ...options.headers
      }
    })
  } catch(error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Сервер отвечает слишком долго. Попробуйте ещё раз.',null)
    }
    throw new ApiError('Не удалось связаться с сервером. Проверьте подключение и попробуйте снова.',null)
  } finally {
    globalThis.clearTimeout(timeout)
  }

  if (!response.ok) {
    let message='Не удалось выполнить действие'
    try {
      const body=await response.json()
      message=typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((error:{loc?:string[];msg?:string}) => `${error.loc?.slice(1).join('.') ?? ''}: ${error.msg ?? 'Некорректное значение'}`).join('; ') : body.message || message
    } catch { /* no JSON error */ }
    throw new ApiError(message,response.status)
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') return undefined as T
  const raw=await response.text()
  if (!raw) return undefined as T
  try {
    return JSON.parse(raw) as T
  } catch {
    throw new ApiError('Сервер вернул ответ в неожиданном формате.',response.status)
  }
}
const demoHomes = () => [...demoApartments, ...read<Apartment[]>(homesKey, [])]
async function imageData(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', 0.72)
}
let recommendationSequence=0
export const api = {
  session: getSession,
  async recommend(input: RecommendationRequest): Promise<RecommendationResponse> {
    const sequence=++recommendationSequence
    const response = isDemo ? (await delay(), demoRecommend(input)) : mapBackendRecommendation(await request<BackendRecommendationResponse>('/recommendations', { method:'POST', body:JSON.stringify(backendRecommendationPayload(input)) }))
    if (sequence === recommendationSequence) rememberRecommendation(response)
    return response
  },
  async event(payload: InteractionPayload): Promise<void> {
    if (isDemo) { logDemoEvent(payload); return }
    // Event ingestion is not provided by the live backend.
  },
  async list(): Promise<Apartment[]> {
    if (isDemo) {
      await delay()
      return demoHomes().filter(x => x.status === 'published').map(withLocalHousingMedia)
    }
    // The existing UI filters and maps the whole catalog. Consume all API pages,
    // never silently truncate it to the first 20/100 records.
    const items:Apartment[]=[]
    let offset=0
    while (true) {
      const page=await request<BackendPage>(`/apartments?limit=100&offset=${offset}`)
      items.push(...page.items.map(mapBackendApartment))
      offset+=page.items.length
      if (!page.items.length || offset >= page.total) return items
    }
  },
  async geoObjects(): Promise<GeoObject[]> { if (isDemo) { await delay(); return normalizeGeoObjects(demoGeoRows) } return normalizeGeoObjects(await request<unknown>('/geo-objects')) },
  async districtStats(): Promise<DistrictStats[]> {
    if (isDemo) {
      await delay()
      return buildDistrictStats(demoHomes().filter(x => x.status === 'published').map(withLocalHousingMedia))
    }
    return buildDistrictStats(await api.list())
  },
  async districts():Promise<District[]> {
    if (isDemo) return [...new Map(demoHomes().map(home => [home.district.id,home.district])).values()]
    return (await request<BackendDistrict[]>('/districts')).map(mapBackendDistrict)
  },
  async demandProfile(): Promise<SharedDemandProfile|null> { return isDemo ? loadDemandProfileForDemo() : null },
  async saveDemandProfile(profile:SharedDemandProfile): Promise<SharedDemandProfile> {
    if (isDemo) return profile
    throw new ApiError('Публикация профиля поиска пока недоступна.')
  },
  async deleteDemandProfile():Promise<void> {},
  async proStatus():Promise<ProAccountStatus> { return {user_id:getSession()?.user.id || '',status:isDemo ? 'active' : 'disabled'} },
  async startProTrial():Promise<ProAccountStatus> { throw new ApiError('GeoDom Pro пока недоступен.') },
  async proLeads(_apartmentId:string):Promise<Array<{lead:ProLead;score:number;reasons:string[];stage:LeadStage}>> { return [] },
  async setProLeadStage(_apartmentId:string,_leadId:string,_stage:LeadStage):Promise<void> { throw new ApiError('GeoDom Pro пока недоступен.') },
  async promotion(_apartmentId:string):Promise<{apartment_id:number;status:string;starts_at:string;ends_at:string}|null> { return null },
  async promote(_apartmentId:string,_days=7):Promise<void> { throw new ApiError('Продвижение пока недоступно.') },
  async cancelPromotion(_apartmentId:string):Promise<void> { throw new ApiError('Продвижение пока недоступно.') },
  async detail(id: string): Promise<Apartment> {
    if (isDemo) {
      await delay()
      const item=demoHomes().find(x => x.id === id && x.status !== 'deleted')
      if (!item) throw new Error('Объявление не найдено')
      return withLocalHousingMedia(item)
    }
    return mapBackendApartment(await request<BackendApartment>(`/apartments/${encodeURIComponent(id)}`))
  },
  async mine(): Promise<Apartment[]> { if (isDemo) { await delay(); return demoHomes().filter(x => x.owner_id === getSession()?.user.id && x.status !== 'deleted') } return (await request<BackendApartment[]>('/apartments/my')).map(mapBackendApartment) },
  async register(login: string, password: string): Promise<User> {
    if (!isDemo) return mapBackendUser((await request<{user:{id:number;login:string}}>('/auth/register', { method: 'POST', body: JSON.stringify({ login, password }) })).user)
    await delay(); const users = read<{ user: User; digest: string }[]>(usersKey, [])
    if (users.some(x => x.user.login.toLowerCase() === login.toLowerCase())) throw new Error('Этот логин уже занят')
    const user = { id: createId(), login }; users.push({ user, digest: demoPasswordDigest(password) }); save(usersKey, users); return user
  },
  async login(login: string, password: string): Promise<User> {
    if (!isDemo) return mapBackendUser((await request<{user:{id:number;login:string}}>('/auth/login', { method:'POST',body:JSON.stringify({login,password}) })).user)
    await delay(); const account = read<{ user: User; digest: string }[]>(usersKey, []).find(x => x.user.login.toLowerCase() === login.toLowerCase())
    if (!account || !await matchesDemoPassword(password,account.digest)) throw new Error('Неверный логин или пароль')
    storeSession({ user: account.user }); return account.user
  },
  async currentUser(): Promise<User | null> {
    if (isDemo) return getSession()?.user ?? null
    try {
      return mapBackendUser(await request<{id:number;login:string}>('/auth/me'))
    } catch(error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        storeSession(null)
        return null
      }
      throw error
    }
  },
  async logout() { if (!isDemo) await request<void>('/auth/logout',{method:'POST'}); storeSession(null) },
  async myDetail(id:string):Promise<Apartment> { return isDemo ? api.detail(id) : mapBackendApartment(await request<BackendApartment>(`/apartments/my/${encodeURIComponent(id)}`)) },
  async create(input: ListingInput): Promise<Apartment> {
    if (!isDemo) {
      return mapBackendApartment(await request<BackendApartment>('/apartments', { method:'POST',body:JSON.stringify(backendListingPayload(input)) }))
    }
    const owner = getSession()?.user; if (!owner) throw new Error('Для публикации войдите в аккаунт')
    const districtName=input.district_name || 'Уточняется'
    const item: Apartment = { id: createId(), ...input, house_number: input.address.match(/\d+[а-яА-Я]?\s*$/)?.[0] || '', latitude: 0, longitude: 0, district: { id:districtName === 'Уточняется' ? 'pending' : districtName.toLocaleLowerCase('ru').replace(/\s+/g,'-'), name:districtName, description:districtName === 'Уточняется' ? 'Район не указан.' : 'Район выбран пользователем; сервер сможет перепроверить его по адресу.' }, photos: [], source:'user', created_at: new Date().toISOString(), status:'published', owner_id:owner.id, features: { schools_1km:0, parks_1km:0, kindergartens_1km:0, nearest_school_m:0, nearest_park_m:0, nearest_transport_m:0 }, development_projects:[], recommendation:{ score:null, reasons:[], model_version:'', ml_available:false, warning:'Оценка появится после подключения сервера.' } }
    save(homesKey, [...read<Apartment[]>(homesKey, []), item]); return item
  },
  async update(id: string, input: ListingInput): Promise<Apartment> {
    if (!isDemo) {
      return mapBackendApartment(await request<BackendApartment>(`/apartments/${encodeURIComponent(id)}`, { method:'PATCH',body:JSON.stringify(backendListingPayload(input)) }))
    }
    const items = read<Apartment[]>(homesKey, []); const index = items.findIndex(x => x.id === id && x.owner_id === getSession()?.user.id)
    if (index < 0) throw new Error('Объявление не найдено')
    items[index] = {
      ...items[index],
      ...input,
      district:input.district_name
        ? { ...items[index].district,name:input.district_name,description:'Район выбран пользователем; сервер сможет перепроверить его по адресу.' }
        : items[index].district
    }
    save(homesKey, items); return items[index]
  },
  async hide(id: string): Promise<void> {
    if (!isDemo) { await request(`/apartments/${encodeURIComponent(id)}/hide`, { method:'POST' }); return }
    const items = read<Apartment[]>(homesKey, []); const item = items.find(x => x.id === id && x.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено'); item.status = 'hidden'; save(homesKey, items)
  },
  async publish(id:string):Promise<void> {
    if (!isDemo) { await request(`/apartments/${encodeURIComponent(id)}/publish`,{method:'POST'}); return }
    const items=read<Apartment[]>(homesKey,[])
    const item=items.find(home => home.id === id && home.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено')
    item.status='published'; save(homesKey,items)
  },
  async remove(id:string):Promise<void> {
    if (!isDemo) { await request(`/apartments/${encodeURIComponent(id)}`,{method:'DELETE'}); return }
    const items=read<Apartment[]>(homesKey,[])
    const item=items.find(home => home.id === id && home.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено')
    item.status='deleted'; save(homesKey,items)
  },
  async photos(id:string):Promise<ApartmentPhoto[]> {
    if (isDemo) return (await api.myDetail(id)).photos
    return (await request<BackendPhoto[]>(`/apartments/my/${encodeURIComponent(id)}/photos`)).map(mapBackendPhoto)
  },
  async deletePhoto(id:string,photoId:string):Promise<void> {
    if (!isDemo) { await request(`/apartments/${encodeURIComponent(id)}/photos/${encodeURIComponent(photoId)}`,{method:'DELETE'}); return }
    const items=read<Apartment[]>(homesKey,[])
    const item=items.find(home => home.id === id && home.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено')
    item.photos=item.photos.filter(photo => photo.id !== photoId)
    if (!item.photos.some(photo => photo.is_cover) && item.photos[0]) item.photos[0].is_cover=true
    save(homesKey,items)
  },
  async coverPhoto(id:string,photoId:string):Promise<void> {
    if (!isDemo) { await request(`/apartments/${encodeURIComponent(id)}/photos/${encodeURIComponent(photoId)}/cover`,{method:'POST'}); return }
    const items=read<Apartment[]>(homesKey,[])
    const item=items.find(home => home.id === id && home.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено')
    item.photos.forEach(photo => { photo.is_cover=photo.id === photoId }); save(homesKey,items)
  },
  async upload(id: string, file: File): Promise<void> {
    if (!isDemo) { const data = new FormData(); data.append('file', file); await request(`/apartments/${encodeURIComponent(id)}/photos`, { method:'POST', body:data }); return }
    const items = read<Apartment[]>(homesKey, []); const item = items.find(x => x.id === id && x.owner_id === getSession()?.user.id)
    if (!item) throw new Error('Объявление не найдено'); if (item.photos.length >= 10) throw new Error('Не больше 10 фотографий')
    const order = item.photos.length; item.photos.push({ id:createId(), url:await imageData(file), order, is_cover:order === 0 })
    try { save(homesKey, items) } catch { item.photos.pop(); throw new Error('В браузере закончилось место для фото. Подключите серверное хранилище.') }
  }
}
