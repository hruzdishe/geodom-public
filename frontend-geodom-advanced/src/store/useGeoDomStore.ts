import { create } from 'zustand'
import type { CatalogFilters, RecommendationRequest, User } from '../types'
import {
  defaultCatalogFilters,
  defaultPreferences,
  loadCatalogFilters,
  loadPreferences,
  saveCatalogFilters,
  savePreferences
} from '../lib/preferences'
import { getSavedIds, toggleSavedId } from '../lib/recommendations'
import { migrateLegacyStorage } from '../lib/storage'

migrateLegacyStorage()

const compareKey = 'geodom-compare-apartments-v1'
const maxCompare = 3

function readComparedIds(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(compareKey) || '[]')
    if (!Array.isArray(parsed)) return []
    return [...new Set(parsed.map(String))].slice(0,maxCompare)
  } catch {
    return []
  }
}

function writeComparedIds(ids: string[]) {
  localStorage.setItem(compareKey,JSON.stringify(ids.slice(0,maxCompare)))
}

type ValueOrUpdater<T> = T | ((current:T)=>T)

interface GeoDomState {
  preferences:RecommendationRequest
  filters:CatalogFilters
  filtersOpen:boolean
  workPicking:boolean
  savedIds:string[]
  comparedIds:string[]
  authReady:boolean
  setAuthReady:(ready:boolean)=>void
  user:User|null

  setPreferences:(next:ValueOrUpdater<RecommendationRequest>)=>void
  setFilter:<K extends keyof CatalogFilters>(key:K,value:CatalogFilters[K])=>void
  replaceFilters:(filters:CatalogFilters)=>void
  resetFilters:()=>void
  resetPreferences:()=>void
  setFiltersOpen:(open:boolean)=>void
  setWorkPicking:(active:boolean)=>void
  setWorkLocation:(location:RecommendationRequest['work_location'])=>void

  refreshSavedIds:()=>void
  toggleSaved:(id:string)=>boolean
  toggleCompared:(id:string)=>boolean
  pruneCompared:(availableIds:Iterable<string>)=>void
  clearCompared:()=>void

  setUser:(user:User|null)=>void
}

export const useGeoDomStore = create<GeoDomState>((set,get) => ({
  preferences:loadPreferences(),
  filters:loadCatalogFilters(),
  filtersOpen:false,
  workPicking:false,
  savedIds:getSavedIds(),
  comparedIds:readComparedIds(),
  user:null,
  authReady:false,
  setAuthReady(authReady) { set({authReady}) },

  setPreferences(next) {
    const value = typeof next === 'function'
      ? (next as (current:RecommendationRequest)=>RecommendationRequest)(get().preferences)
      : next
    savePreferences(value)
    set({ preferences:value })
  },

  setFilter(key,value) {
    const filters = { ...get().filters,[key]:value }
    saveCatalogFilters(filters)
    set({ filters })
  },

  replaceFilters(filters) {
    saveCatalogFilters(filters)
    set({ filters })
  },

  resetFilters() {
    saveCatalogFilters(defaultCatalogFilters)
    set({ filters:defaultCatalogFilters })
  },

  resetPreferences() {
    savePreferences(defaultPreferences)
    set({ preferences:defaultPreferences,workPicking:false })
  },

  setFiltersOpen(filtersOpen) {
    set({ filtersOpen })
  },

  setWorkPicking(workPicking) {
    set({ workPicking })
  },

  setWorkLocation(work_location) {
    const preferences = { ...get().preferences,work_location }
    savePreferences(preferences)
    set({ preferences,workPicking:false })
  },

  refreshSavedIds() {
    set({ savedIds:getSavedIds() })
  },

  toggleSaved(id) {
    const active = toggleSavedId(id)
    set({ savedIds:getSavedIds() })
    return active
  },

  toggleCompared(id) {
    const current = get().comparedIds
    const comparedIds = current.includes(id)
      ? current.filter(value => value !== id)
      : current.length >= maxCompare
        ? current
        : [...current,id]
    writeComparedIds(comparedIds)
    set({ comparedIds })
    return comparedIds.includes(id)
  },

  pruneCompared(availableIds) {
    const available = new Set(availableIds)
    const comparedIds = get().comparedIds.filter(id => available.has(id))
    if (comparedIds.length === get().comparedIds.length) return
    writeComparedIds(comparedIds)
    set({ comparedIds })
  },

  clearCompared() {
    writeComparedIds([])
    set({ comparedIds:[] })
  },

  setUser(user) {
    set({ user })
  }
}))

export const geoDomStoreInternals = {
  compareKey,
  maxCompare,
  readComparedIds,
  writeComparedIds
}
