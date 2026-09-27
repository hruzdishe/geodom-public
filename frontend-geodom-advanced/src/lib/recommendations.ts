import { demoApartments } from '../data/demo'
import { cleanText, finiteNumber } from './dataSanitizers'
import type { InteractionPayload, RecommendationItem, RecommendationRequest, RecommendationResponse } from '../types'
import { createId } from './id'

const savedKey = 'geodom-saved-apartments-v1'
const eventKey = 'geodom-demo-events-v1'
const lastKey = import.meta.env.VITE_API_URL ? `geodom-live-recommendation:${import.meta.env.VITE_API_URL}` : 'geodom-last-recommendation-v1'
const clamp = (value: number) => Math.max(0, Math.min(10, value))
const round = (value: number) => Math.round(value * 10) / 10

function read<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || '') as T }
  catch { return fallback }
}

function nullableNumber(value: unknown) {
  return finiteNumber(value)
}

function numberOr(value: unknown, fallback: number) {
  return finiteNumber(value) ?? fallback
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(cleanText).filter((item):item is string => item !== null)
}

function resolveMediaUrl(value: unknown, origin: string): string | null {
  const url = cleanText(value)
  if (!url) return null
  if (!origin) return url
  try { return new URL(url,origin).toString() }
  catch { return null }
}

type RawItem = Omit<Partial<RecommendationItem>, 'scores'> & Pick<RecommendationItem, 'apartment_id'> & { scores?: Partial<RecommendationItem['scores']> }
export function normalizeRecommendation(raw: {
  request_id?:unknown
  model_version?:unknown
  scoring_version?:unknown
  ml_available?:boolean
  warnings?:unknown
  items?:RawItem[]
}, origin:string): RecommendationResponse {
  const keys: Array<keyof RecommendationItem['scores']> = ['schools','parks','transport','ecology','safety','commute','price']
  const items = Array.isArray(raw.items) ? raw.items : []
  return {
    request_id:cleanText(raw.request_id) || createId(),
    model_version:cleanText(raw.model_version) || 'unknown',
    scoring_version:cleanText(raw.scoring_version) || 'unknown',
    ml_available:raw.ml_available ?? true,
    warnings:textList(raw.warnings),
    items:items.map(item => ({
      apartment_id:item.apartment_id,
      title:cleanText(item.title) || 'Объект без названия',
      price:numberOr(item.price,0),
      price_m2:numberOr(item.price_m2,0),
      predicted_price_m2:nullableNumber(item.predicted_price_m2),
      score:nullableNumber(item.score),
      scores:Object.fromEntries(keys.map(key => [key,nullableNumber(item.scores?.[key])])) as RecommendationItem['scores'],
      contributions:item.contributions
        ? Object.fromEntries(keys.flatMap(key => {
            const value = nullableNumber(item.contributions?.[key])
            return value === null ? [] : [[key,value]]
          })) as RecommendationItem['contributions']
        : undefined,
      commute_minutes:nullableNumber(item.commute_minutes),
      reasons:textList(item.reasons),
      warnings:textList(item.warnings),
      cover_image_url:resolveMediaUrl(item.cover_image_url,origin)
    }))
  }
}

export function demoRecommend(input: RecommendationRequest): RecommendationResponse {
  const warnings = ['Демонстрационный расчёт: ML-модель и прогноз цены пока не подключены.', 'Нет данных об экологии и безопасности; эти приоритеты не участвуют в оценке.']
  if (input.work_location) warnings.push('В демо нет маршрутных данных: время до работы и ограничение по поездке не учитываются.')
  if (input.down_payment) warnings.push('Первоначальный взнос сохранён в запросе, но не влияет на оценку в демо.')
  const eligible = demoApartments.filter(home => !input.budget_max || home.price <= input.budget_max)
  const items: RecommendationItem[] = eligible.map(home => {
    const f = home.features
    const schools = round(clamp((f.schools_1km ?? 0) * 2 + (f.nearest_school_m !== null && f.nearest_school_m < 500 ? 2 : 0)))
    const parks = round(clamp((f.parks_1km ?? 0) * 2.4 + (f.nearest_park_m !== null && f.nearest_park_m < 500 ? 2 : 0)))
    const transport = round(clamp(10 - (f.nearest_transport_m ?? 800) / 80))
    const affordability = round(clamp(input.budget_max ? 10 - 3 * home.price / input.budget_max : 8))
    const schoolWeight = input.priorities.schools + Math.min(2, input.family.children)
    const parkWeight = input.priorities.parks
    const transportWeight = input.priorities.transport
    const weightTotal = schoolWeight + parkWeight + transportWeight + 1
    const schoolContribution = schools * schoolWeight / weightTotal
    const parkContribution = parks * parkWeight / weightTotal
    const transportContribution = transport * transportWeight / weightTotal
    const priceContribution = affordability / weightTotal
    const score = round(schoolContribution + parkContribution + transportContribution + priceContribution)
    return {
      apartment_id:home.id,
      title:home.title,
      price:home.price,
      price_m2:Math.round(home.price/home.area),
      predicted_price_m2:null,
      score,
      scores:{ schools, parks, transport, ecology:null, safety:null, commute:null, price:affordability },
      contributions:{
        schools:round(schoolContribution),
        parks:round(parkContribution),
        transport:round(transportContribution),
        price:round(priceContribution)
      },
      commute_minutes:null,
      reasons:[`${f.schools_1km} школы рядом (до 1 км)`, `Парк в ${f.nearest_park_m} м`, `Транспорт в ${f.nearest_transport_m} м`],
      warnings:[],
      cover_image_url:home.photos[0]?.url || null
    }
  }).sort((a,b) => (b.score ?? -1)-(a.score ?? -1))
  return {
    request_id:createId(),
    model_version:'demo-no-model',
    scoring_version:'demo-weighted-v1',
    ml_available:false,
    warnings,
    items:items.slice(0,input.limit)
  }
}

export function logDemoEvent(payload: InteractionPayload): void {
  const events = read<Array<InteractionPayload & { timestamp:string }>>(eventKey,[])
  events.push({ ...payload, timestamp:new Date().toISOString() })
  localStorage.setItem(eventKey,JSON.stringify(events.slice(-500)))
}

export function readDemoEvents() {
  return read<Array<InteractionPayload & { timestamp:string }>>(eventKey,[])
}

export function rememberRecommendation(response: RecommendationResponse): void {
  localStorage.setItem(lastKey,JSON.stringify(response))
}

export function loadLastRecommendation(): RecommendationResponse | null {
  try {
    const raw = JSON.parse(localStorage.getItem(lastKey) || '')
    if (!raw || !Array.isArray(raw.items)) return null
    return normalizeRecommendation(raw,'')
  } catch {
    return null
  }
}

export function getLastRecommendationItem(id: string): { response:RecommendationResponse; item:RecommendationItem } | null {
  const response = loadLastRecommendation()
  if (!response) return null
  const item = response.items.find(candidate => String(candidate.apartment_id) === id)
  return item ? { response,item } : null
}

export function getSavedIds(): string[] {
  return read<string[]>(savedKey,[])
}

export function toggleSavedId(id: string): boolean {
  const current = getSavedIds()
  const next = current.includes(id) ? current.filter(value => value !== id) : [...current,id]
  localStorage.setItem(savedKey,JSON.stringify(next))
  return next.includes(id)
}
