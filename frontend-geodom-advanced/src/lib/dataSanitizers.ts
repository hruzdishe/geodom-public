const EMPTY_TEXT = new Set(['', 'nan', 'none', 'null', 'undefined', '<na>', 'nat', 'n/a', '-'])

export function cleanText(value: unknown): string | null {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return EMPTY_TEXT.has(text.toLowerCase()) ? null : text
}

export function finiteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const number = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(number) ? number : null
}

export function booleanValue(value: unknown): boolean | null {
  if (typeof value === 'boolean') return value
  const text = cleanText(value)?.toLowerCase()
  if (!text) return null
  if (['true','1','yes','да'].includes(text)) return true
  if (['false','0','no','нет'].includes(text)) return false
  return null
}

export function validCoordinate(lat: unknown, lon: unknown): { lat: number; lon: number } | null {
  const latitude = finiteNumber(lat)
  const longitude = finiteNumber(lon)
  if (latitude === null || longitude === null || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return { lat:latitude, lon:longitude }
}

export function parseWktPoint(value: unknown): { lat: number; lon: number } | null {
  const text = cleanText(value)
  if (!text) return null
  const match = /^POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)$/i.exec(text)
  if (!match) return null
  return validCoordinate(Number(match[2]), Number(match[1]))
}

function pointFromRaw(raw: Record<string, unknown>): { lat:number; lon:number } | null {
  const direct = validCoordinate(raw.latitude ?? raw.lat,raw.longitude ?? raw.lon ?? raw.lng)
  if (direct) return direct

  if (raw.geometry && typeof raw.geometry === 'object' && !Array.isArray(raw.geometry)) {
    const geometry = raw.geometry as { type?:unknown; coordinates?:unknown }
    if (String(geometry.type).toLowerCase() === 'point' && Array.isArray(geometry.coordinates) && geometry.coordinates.length >= 2) {
      const point = validCoordinate(geometry.coordinates[1],geometry.coordinates[0])
      if (point) return point
    }
  }

  return parseWktPoint(raw.geometry)
}

export interface GeoObject {
  id: string
  osmType: string | null
  category: string
  subcategory: string | null
  name: string
  address: string | null
  locationLabel: string | null
  lat: number
  lon: number
  source: string | null
  sourceUrl: string | null
  sourceUpdatedAt: string | null
  collectedAt: string | null
  addressDistanceM: number | null
  addressIsApproximate: boolean | null
}

export function normalizeGeoObject(raw: Record<string, unknown>): GeoObject | null {
  const point = pointFromRaw(raw)
  if (!point) return null

  const id = cleanText(raw.osm_id) || cleanText(raw.source_id)
  if (!id) return null

  const category = cleanText(raw.category) || 'other'
  const subcategory = cleanText(raw.subcategory)
  const locationLabel = cleanText(raw.location_label)
  const name = cleanText(raw.name) || locationLabel || subcategory || 'Объект инфраструктуры'
  const distance = finiteNumber(raw.address_distance_m)

  return {
    id,
    osmType:cleanText(raw.osm_type),
    category,
    subcategory,
    name,
    address:cleanText(raw.address) || cleanText(raw.address_original),
    locationLabel,
    lat:point.lat,
    lon:point.lon,
    source:cleanText(raw.source),
    sourceUrl:cleanText(raw.source_url),
    sourceUpdatedAt:cleanText(raw.source_updated_at),
    collectedAt:cleanText(raw.collected_at),
    addressDistanceM:distance !== null && distance >= 0 ? distance : null,
    addressIsApproximate:booleanValue(raw.address_is_approximate)
  }
}

export function normalizeGeoObjects(raw: unknown): GeoObject[] {
  const rows = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && !Array.isArray(raw)
      ? ((raw as { items?:unknown; data?:unknown; results?:unknown }).items
        ?? (raw as { data?:unknown }).data
        ?? (raw as { results?:unknown }).results)
      : []

  if (!Array.isArray(rows)) return []
  return rows
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item))
    .map(normalizeGeoObject)
    .filter((item): item is GeoObject => item !== null)
}
