export type SpatialBounds = {
  minLat:number
  maxLat:number
  minLon:number
  maxLon:number
}

type SpatialEntry<T> = {
  item:T
  lat:number
  lon:number
}

export interface SpatialIndex<T> {
  readonly size:number
  query:(bounds:SpatialBounds|null,options?:{ padding?:number;limit?:number })=>T[]
}

function cellKey(latCell:number,lonCell:number) {
  return `${latCell}:${lonCell}`
}

export function createSpatialIndex<T>(
  items:readonly T[],
  getPoint:(item:T)=>{ lat:number;lon:number }|null,
  cellSize=.02
):SpatialIndex<T> {
  if (!Number.isFinite(cellSize) || cellSize <= 0) throw new Error('cellSize must be positive')

  const cells = new Map<string,SpatialEntry<T>[]>()
  const all:SpatialEntry<T>[] = []

  for (const item of items) {
    const point = getPoint(item)
    if (!point || !Number.isFinite(point.lat) || !Number.isFinite(point.lon)) continue
    const entry = { item,lat:point.lat,lon:point.lon }
    all.push(entry)
    const latCell = Math.floor(point.lat/cellSize)
    const lonCell = Math.floor(point.lon/cellSize)
    const key = cellKey(latCell,lonCell)
    const bucket = cells.get(key)
    if (bucket) bucket.push(entry)
    else cells.set(key,[entry])
  }

  return {
    size:all.length,
    query(bounds,options={}) {
      const limit = options.limit && options.limit > 0 ? Math.floor(options.limit) : Infinity
      if (!bounds) return all.slice(0,limit).map(entry => entry.item)

      const padding = Math.max(0,options.padding ?? 0)
      const latPad = (bounds.maxLat-bounds.minLat)*padding
      const lonPad = (bounds.maxLon-bounds.minLon)*padding
      const minLat = bounds.minLat-latPad
      const maxLat = bounds.maxLat+latPad
      const minLon = bounds.minLon-lonPad
      const maxLon = bounds.maxLon+lonPad

      const minLatCell = Math.floor(minLat/cellSize)
      const maxLatCell = Math.floor(maxLat/cellSize)
      const minLonCell = Math.floor(minLon/cellSize)
      const maxLonCell = Math.floor(maxLon/cellSize)
      const result:T[] = []

      for (let latCell=minLatCell;latCell<=maxLatCell;latCell++) {
        for (let lonCell=minLonCell;lonCell<=maxLonCell;lonCell++) {
          const bucket = cells.get(cellKey(latCell,lonCell))
          if (!bucket) continue
          for (const entry of bucket) {
            if (entry.lat < minLat || entry.lat > maxLat || entry.lon < minLon || entry.lon > maxLon) continue
            result.push(entry.item)
            if (result.length >= limit) return result
          }
        }
      }

      return result
    }
  }
}
