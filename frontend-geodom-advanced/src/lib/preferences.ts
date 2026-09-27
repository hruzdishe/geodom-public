import type { CatalogFilters, RecommendationRequest } from '../types'

const preferenceKey = 'geodom-recommendation-preferences-v1'
const filtersKey = 'geodom-catalog-filters-v1'

export const defaultPreferences: RecommendationRequest = {
  budget_max:12000000,
  down_payment:2000000,
  family:{ adults:2, children:1 },
  work_location:null,
  max_commute_minutes:40,
  priorities:{ schools:4, parks:4, transport:4, ecology:3, safety:3 },
  limit:20
}

export const defaultCatalogFilters: CatalogFilters = {
  district:'',
  maxPrice:0,
  rooms:0,
  minArea:0,
  yearFrom:0,
  buildingType:'',
  onlyWithPhotos:false,
  query:'',
  sort:'recommended'
}

export function validatePreferences(value: RecommendationRequest): string | null {
  if (!Number.isFinite(value.budget_max) || value.budget_max <= 0) return 'Укажите бюджет больше нуля'
  if (!Number.isFinite(value.down_payment) || value.down_payment < 0) return 'Укажите корректный первоначальный взнос'
  if (value.down_payment > value.budget_max) return 'Первоначальный взнос не может превышать бюджет'
  if (value.family.adults < 1) return 'Укажите хотя бы одного взрослого'
  if (value.work_location && (!Number.isFinite(value.work_location.lat) || !Number.isFinite(value.work_location.lon))) return 'Выберите корректную точку работы на карте'
  return null
}

export function loadPreferences(): RecommendationRequest {
  try {
    const saved = JSON.parse(localStorage.getItem(preferenceKey) || '') as RecommendationRequest
    return saved && !validatePreferences(saved) && saved.priorities ? saved : defaultPreferences
  } catch {
    return defaultPreferences
  }
}

export function savePreferences(value: RecommendationRequest) {
  localStorage.setItem(preferenceKey, JSON.stringify(value))
}

export function loadCatalogFilters(): CatalogFilters {
  try {
    const saved = JSON.parse(localStorage.getItem(filtersKey) || '') as Partial<CatalogFilters>
    const maxPrice = Number(saved.maxPrice)
    const rooms = Number(saved.rooms)
    const minArea = Number(saved.minArea)
    const yearFrom = Number(saved.yearFrom)
    return {
      ...defaultCatalogFilters,
      ...saved,
      maxPrice:Number.isFinite(maxPrice) && maxPrice >= 0 ? maxPrice : 0,
      rooms:Number.isInteger(rooms) && rooms >= -1 ? rooms : 0,
      minArea:Number.isFinite(minArea) && minArea >= 0 ? minArea : 0,
      yearFrom:Number.isInteger(yearFrom) && yearFrom >= 0 ? yearFrom : 0,
      buildingType:typeof saved.buildingType === 'string' ? saved.buildingType : '',
      onlyWithPhotos:Boolean(saved.onlyWithPhotos),
      sort:['recommended','price_asc','price_desc','area_desc'].includes(String(saved.sort)) ? saved.sort as CatalogFilters['sort'] : 'recommended'
    }
  } catch {
    return defaultCatalogFilters
  }
}

export function saveCatalogFilters(value: CatalogFilters) {
  localStorage.setItem(filtersKey, JSON.stringify(value))
}
