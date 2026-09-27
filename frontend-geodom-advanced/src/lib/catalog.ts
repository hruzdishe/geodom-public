import type { Apartment, CatalogFilters, ListingInput, RecommendationRequest } from '../types'
import { estimateCommuteMinutes } from './commute'
import { isKrasnoyarskDistrict } from './krasnoyarsk'

export function filterApartments(items:Apartment[],filters:CatalogFilters,commute?:Pick<RecommendationRequest,'work_location'|'max_commute_minutes'>) {
  const query=filters.query.trim().toLocaleLowerCase('ru')
  return items.filter(apartment => {
    const minutes=commute?.work_location ? estimateCommuteMinutes(apartment.latitude,apartment.longitude,commute.work_location) : null
    const commuteMatch=!commute?.work_location || (minutes !== null && minutes <= commute.max_commute_minutes)
    const photoCount=apartment.photo_count ?? apartment.photos.length
    const roomsMatch=!filters.rooms || (filters.rooms === -1 ? apartment.rooms === 0 : filters.rooms >= 4 ? apartment.rooms >= 4 : apartment.rooms === filters.rooms)
    const yearMatch=!filters.yearFrom || (apartment.building_year != null && apartment.building_year >= filters.yearFrom)
    const buildingTypeMatch=!filters.buildingType || apartment.building_type === filters.buildingType
    const searchText=`${apartment.title} ${apartment.address} ${apartment.district.name} ${apartment.complex_name || ''}`.toLocaleLowerCase('ru')

    return apartment.status === 'published'
      && (!filters.dealType || (apartment.deal_type ?? 'sale') === filters.dealType)
      && (filters.dealType !== 'rent' || !filters.rentPeriod || apartment.rent_period === filters.rentPeriod)
      && (!filters.district || apartment.district.name === filters.district)
      && (!filters.maxPrice || apartment.price <= filters.maxPrice)
      && roomsMatch && commuteMatch
      && (!filters.minArea || apartment.area >= filters.minArea)
      && yearMatch
      && buildingTypeMatch
      && (!filters.onlyWithPhotos || photoCount > 0)
      && (!query || searchText.includes(query))
  }).sort((a,b) => filters.sort === 'price_asc'
    ? a.price-b.price
    : filters.sort === 'price_desc'
      ? b.price-a.price
      : filters.sort === 'area_desc'
        ? b.area-a.area
        : (b.recommendation.score ?? -1)-(a.recommendation.score ?? -1))
}

export function validateApartment(input:ListingInput,requireDistrict=true):string[] {
  const errors:string[]=[]
  if (!input.title.trim()) errors.push('Укажите название объявления')
  if (!input.address.trim()) errors.push('Укажите адрес')
  if (requireDistrict && !isKrasnoyarskDistrict(input.district_name)) errors.push('Выберите один из 7 районов Красноярска')
  if (!Number.isFinite(input.price) || input.price <= 0) errors.push('Цена должна быть больше нуля')
  if (!Number.isFinite(input.area) || input.area <= 0) errors.push('Площадь должна быть больше нуля')
  if (!Number.isInteger(input.rooms) || input.rooms < 0) errors.push('Укажите корректное число комнат')
  if (!Number.isInteger(input.total_floors) || input.total_floors < 1) errors.push('Укажите этажность дома')
  if (!Number.isInteger(input.floor) || input.floor < 1) errors.push('Укажите корректный этаж')
  if (input.floor > input.total_floors) errors.push('Этаж не может превышать этажность дома')
  return errors
}

const integerFormatter=new Intl.NumberFormat('ru-RU')
const decimalFormatter=new Intl.NumberFormat('ru-RU',{ maximumFractionDigits:1 })

export const price=(n:number) => integerFormatter.format(n)+' ₽'
export const area=(n:number) => decimalFormatter.format(n)+' м²'
export const distance=(n:number|null) => n === null ? 'нет данных' : n < 1000 ? `${n} м` : `${decimalFormatter.format(n/1000)} км`
