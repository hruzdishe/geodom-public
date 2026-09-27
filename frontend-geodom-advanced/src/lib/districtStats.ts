import { KRASNOYARSK_DISTRICTS, type KrasnoyarskDistrictName } from './krasnoyarsk'
import type { Apartment } from '../types'

export type DistrictStats = {
  id:string
  name:KrasnoyarskDistrictName
  count:number
  medianPrice:number|null
  medianPriceM2:number|null
  medianArea:number|null
  averageScore:number|null
  photoCoverage:number|null
  minPrice:number|null
  maxPrice:number|null
}

function median(values:number[]) {
  const sorted=values.filter(Number.isFinite).sort((a,b) => a-b)
  if (!sorted.length) return null
  const middle=Math.floor(sorted.length/2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle-1]+sorted[middle])/2
}

function score10(value:number|null) {
  if (value === null || !Number.isFinite(value)) return null
  return value > 10 ? value/10 : value
}

export function buildDistrictStats(items:Apartment[]):DistrictStats[] {
  return KRASNOYARSK_DISTRICTS.map(district => {
    const apartments=items.filter(item => item.status === 'published' && item.district.name === district.name)
    const prices=apartments.map(item => item.price).filter(value => Number.isFinite(value) && value > 0)
    const priceM2=apartments.map(item => item.price_m2 ?? (item.area > 0 ? item.price/item.area : NaN)).filter(Number.isFinite)
    const areas=apartments.map(item => item.area).filter(value => Number.isFinite(value) && value > 0)
    const scores=apartments.map(item => score10(item.recommendation.score)).filter((value):value is number => value !== null)
    const withPhotos=apartments.filter(item => (item.photo_count ?? item.photos.length) > 0).length

    return {
      id:district.id,
      name:district.name,
      count:apartments.length,
      medianPrice:median(prices),
      medianPriceM2:median(priceM2),
      medianArea:median(areas),
      averageScore:scores.length ? scores.reduce((sum,value) => sum+value,0)/scores.length : null,
      photoCoverage:apartments.length ? withPhotos/apartments.length : null,
      minPrice:prices.length ? Math.min(...prices) : null,
      maxPrice:prices.length ? Math.max(...prices) : null
    }
  })
}
