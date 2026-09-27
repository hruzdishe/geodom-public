import { filterApartments } from './catalog'
import type { Apartment,CatalogFilters,RecommendationRequest } from '../types'

export type SavedSearch={
  id:string
  label:string
  createdAt:string
  updatedAt:string
  preferences:RecommendationRequest
  filters:CatalogFilters
  seenApartmentIds:string[]
}

const key='geodom-saved-searches-v1'
const limit=10

function createId() {
  return globalThis.crypto?.randomUUID?.() ?? `search-${Date.now()}-${Math.random().toString(36).slice(2,9)}`
}

export function loadSavedSearches():SavedSearch[] {
  try {
    const parsed=JSON.parse(localStorage.getItem(key) || '[]') as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((item):item is SavedSearch => Boolean(item && typeof item === 'object' && typeof (item as SavedSearch).id === 'string'))
      .slice(0,limit)
  } catch {
    return []
  }
}

function persist(items:SavedSearch[]) {
  localStorage.setItem(key,JSON.stringify(items.slice(0,limit)))
}

export function savedSearchMatches(search:SavedSearch,items:Apartment[]) {
  return filterApartments(items,search.filters)
}

export function savedSearchNewMatches(search:SavedSearch,items:Apartment[]) {
  const seen=new Set(search.seenApartmentIds)
  return savedSearchMatches(search,items).filter(item => !seen.has(String(item.id)))
}

export function createSavedSearch({
  label,
  preferences,
  filters,
  items
}:{
  label:string
  preferences:RecommendationRequest
  filters:CatalogFilters
  items:Apartment[]
}) {
  const now=new Date().toISOString()
  const search:SavedSearch={
    id:createId(),
    label:label.trim() || 'Мой поиск',
    createdAt:now,
    updatedAt:now,
    preferences:structuredClone(preferences),
    filters:structuredClone(filters),
    seenApartmentIds:savedSearchMatches({ id:'',label:'',createdAt:now,updatedAt:now,preferences,filters,seenApartmentIds:[] },items).map(item => String(item.id))
  }
  persist([search,...loadSavedSearches()])
  return search
}

export function markSavedSearchSeen(id:string,items:Apartment[]) {
  const searches=loadSavedSearches()
  const next=searches.map(search => search.id === id
    ? {
        ...search,
        seenApartmentIds:savedSearchMatches(search,items).map(item => String(item.id)),
        updatedAt:new Date().toISOString()
      }
    : search)
  persist(next)
  return next
}

export function deleteSavedSearch(id:string) {
  const next=loadSavedSearches().filter(search => search.id !== id)
  persist(next)
  return next
}

export const savedSearchStorageKey=key
export const maxSavedSearches=limit
