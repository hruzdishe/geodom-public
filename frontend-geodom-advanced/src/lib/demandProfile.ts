import type { CatalogFilters, RecommendationRequest, User } from '../types'
import type { ProLead } from './pro'

export type SharedDemandProfile={
  id:string
  userId:string
  name:string
  contact:string
  consentToContact:boolean
  budgetMax:number
  districts:string[]
  roomsMin:number
  roomsMax:number
  maxCommuteMinutes:number
  priorities:string[]
  workLocation:{lat:number;lon:number}|null
  createdAt:string
  updatedAt:string
}

const key='geodom-shared-demand-profile-v1'

function id() {
  return globalThis.crypto?.randomUUID?.() ?? `demand-${Date.now()}-${Math.random().toString(36).slice(2,9)}`
}

function priorityLabels(preferences:RecommendationRequest) {
  const pairs:Array<[keyof RecommendationRequest['priorities'],string]>=[
    ['schools','Школы'],
    ['parks','Парки'],
    ['transport','Транспорт'],
    ['ecology','Экология'],
    ['safety','Безопасность']
  ]
  return pairs
    .filter(([key]) => preferences.priorities[key] >= 4)
    .sort((a,b) => preferences.priorities[b[0]]-preferences.priorities[a[0]])
    .map(([,label]) => label)
}

function roomRange(filters:CatalogFilters) {
  if (!filters.rooms) return { min:1,max:4 }
  if (filters.rooms >= 4) return { min:4,max:8 }
  return { min:filters.rooms,max:filters.rooms }
}

export function buildSharedDemandProfile({
  current,
  user,
  contact,
  consentToContact,
  preferences,
  filters
}:{
  current:SharedDemandProfile|null
  user:User
  contact:string
  consentToContact:boolean
  preferences:RecommendationRequest
  filters:CatalogFilters
}):SharedDemandProfile {
  const rooms=roomRange(filters)
  const now=new Date().toISOString()
  return {
    id:current?.id ?? id(),
    userId:user.id,
    name:user.login,
    contact:contact.trim(),
    consentToContact,
    budgetMax:preferences.budget_max,
    districts:filters.district ? [filters.district] : [],
    roomsMin:rooms.min,
    roomsMax:rooms.max,
    maxCommuteMinutes:preferences.max_commute_minutes,
    priorities:priorityLabels(preferences),
    workLocation:preferences.work_location,
    createdAt:current?.createdAt ?? now,
    updatedAt:now
  }
}

export function loadSharedDemandProfile():SharedDemandProfile|null {
  try {
    const raw=localStorage.getItem(key)
    if (!raw) return null
    const value=JSON.parse(raw) as SharedDemandProfile
    if (!value || typeof value.id !== 'string' || typeof value.userId !== 'string') return null
    return value
  } catch {
    return null
  }
}

export function saveSharedDemandProfile(profile:SharedDemandProfile) {
  localStorage.setItem(key,JSON.stringify(profile))
}

export function revokeSharedDemandProfile() {
  const current=loadSharedDemandProfile()
  if (!current) return null
  const next={...current,consentToContact:false,updatedAt:new Date().toISOString()}
  saveSharedDemandProfile(next)
  return next
}

export function clearSharedDemandProfile() {
  localStorage.removeItem(key)
}

export function sharedDemandProfileToLead(profile:SharedDemandProfile):ProLead {
  return {
    id:`shared:${profile.id}`,
    name:profile.name,
    intent:'buy',
    budgetMax:profile.budgetMax,
    districts:profile.districts,
    roomsMin:profile.roomsMin,
    roomsMax:profile.roomsMax,
    maxCommuteMinutes:profile.maxCommuteMinutes,
    priorities:profile.priorities,
    workLabel:profile.workLocation ? `${profile.workLocation.lat.toFixed(4)}, ${profile.workLocation.lon.toFixed(4)}` : 'Место работы не задано',
    createdAt:profile.createdAt,
    consentToContact:profile.consentToContact,
    contact:profile.contact,
    source:'local'
  }
}

export const demandProfileStorageKey=key
