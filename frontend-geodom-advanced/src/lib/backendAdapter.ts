import type { Apartment, ApartmentPhoto, District, ListingInput, RecommendationItem, RecommendationRequest, RecommendationResponse, User } from '../types'
import { finiteNumber, validCoordinate } from './dataSanitizers'

type Numeric = number | string
export interface BackendDistrict {
  id:number; name:string; description?:string|null
  center_latitude?:Numeric|null; center_longitude?:Numeric|null
}
export interface BackendPhoto { id:number; url:string|null; position:number; is_cover:boolean }
export interface BackendApartment {
  id:number; title:string; price:Numeric; area:Numeric; rooms:number; floor:number; total_floors:number
  address:string; latitude?:Numeric|null; longitude?:Numeric|null; district:BackendDistrict
  description?:string|null; house_number?:string|null; photos?:BackendPhoto[]; created_at:string
  status:Apartment['status']; owner_id?:number|null; origin?:'seed'|'user'; source?:string
  deal_type:'sale'|'rent'; rent_period:'day'|'month'|null; building_year?:number|null
  source_url?:string|null; complex_name?:string|null
  features?:Partial<Record<keyof Apartment['features'],Numeric|null>>|null
}
export interface BackendPage { items:BackendApartment[]; total:number; limit:number; offset:number }
export interface BackendRecommendationResponse {
  request_id:string; model_version:string; scoring_version:string; fallback_used:boolean
  status:string; eligible_count:number; returned_count:number; limitations:string[]
  unsupported_priorities:Array<{priority?:string; reason?:string}>
  items:Array<{
    rank:number; apartment:BackendApartment; score:number|null; score_coverage:number; scoring_status:string
    components:Array<{priority:string; score:number|null; contribution_points:number; explanation:string; status:string}>
    commute:{estimated_minutes?:number|null; badge?:string|null; limitation?:string|null}|null
  }>
}

export const mapBackendUser = (raw:{id:number; login:string}):User => ({id:String(raw.id),login:raw.login})
export const mapBackendDistrict = (raw:BackendDistrict):District => ({id:String(raw.id),name:raw.name,description:raw.description ?? ''})
export const mapBackendPhoto = (raw:BackendPhoto):ApartmentPhoto => ({id:String(raw.id),url:raw.url ?? '',order:raw.position,is_cover:raw.is_cover})

export function mapBackendApartment(raw:BackendApartment):Apartment {
  const coordinates=validCoordinate(raw.latitude,raw.longitude)
  const features=raw.features
  const photos=(raw.photos ?? []).map(mapBackendPhoto).filter(photo => !!photo.url)
    .sort((a,b) => Number(b.is_cover)-Number(a.is_cover) || a.order-b.order)
  return {
    id:String(raw.id),title:raw.title,price:Number(raw.price),area:Number(raw.area),rooms:raw.rooms,
    floor:raw.floor,total_floors:raw.total_floors,address:raw.address,house_number:raw.house_number ?? '',
    latitude:coordinates?.lat ?? null,longitude:coordinates?.lon ?? null,district:mapBackendDistrict(raw.district),
    description:raw.description ?? '',photos,photo_count:photos.length,created_at:raw.created_at,status:raw.status,
    owner_id:raw.owner_id == null ? null : String(raw.owner_id),source:raw.origin ?? (raw.owner_id == null ? 'seed' : 'user'),
    upstream_source:raw.source,source_url:raw.source_url ?? undefined,complex_name:raw.complex_name ?? undefined,
    deal_type:raw.deal_type,rent_period:raw.rent_period,building_year:raw.building_year ?? undefined,
    features:{schools_1km:finiteNumber(features?.schools_1km),parks_1km:finiteNumber(features?.parks_1km),
      kindergartens_1km:finiteNumber(features?.kindergartens_1km),nearest_school_m:finiteNumber(features?.nearest_school_m),
      nearest_park_m:finiteNumber(features?.nearest_park_m),nearest_transport_m:finiteNumber(features?.nearest_transport_m)},
    development_projects:[],recommendation:{score:null,reasons:[],model_version:'',ml_available:false}
  }
}

export function backendListingPayload(input:ListingInput) {
  return {title:input.title,address:input.address,price:input.price,area:input.area,rooms:input.rooms,
    floor:input.floor,total_floors:input.total_floors,description:input.description,
    deal_type:input.deal_type ?? 'sale',rent_period:input.deal_type === 'rent' ? input.rent_period ?? 'month' : null}
}

export function backendRecommendationPayload(input:RecommendationRequest) {
  const filters=input.catalog_filters
  const rooms=filters?.rooms ?? 0
  const offerType=filters?.dealType || 'sale'
  const priceMax=offerType === 'rent' ? filters?.maxPrice || undefined : Math.min(input.budget_max,filters?.maxPrice || Infinity)
  return {price_max:priceMax == null ? undefined : Math.round(priceMax),offer_type:offerType,priorities:input.priorities,
    rooms:rooms === -1 ? [0] : rooms >= 4 ? Array.from({length:17},(_,index) => index+4) : rooms > 0 ? [rooms] : [],
    districts:filters?.district ? [filters.district] : [],
    // Age is not collected by this UI; do not invent a child age group.
    children_age_groups:[],work:input.work_location ? {...input.work_location,max_minutes:input.max_commute_minutes} : null,
    limit:input.limit}
}

const score10 = (score:number|null) => score === null ? null : score/10
export function mapBackendRecommendation(raw:BackendRecommendationResponse):RecommendationResponse {
  return {
    request_id:raw.request_id,model_version:raw.model_version,scoring_version:raw.scoring_version,ml_available:false,
    warnings:[...(raw.limitations ?? []),...(raw.unsupported_priorities ?? []).flatMap(item => item.reason ? [item.reason] : []),
      ...(raw.fallback_used ? ['Скоринг временно недоступен: показаны варианты по базовым фильтрам.'] : [])],
    items:[...raw.items].sort((a,b) => a.rank-b.rank).map(item => {
      const apartment=mapBackendApartment(item.apartment)
      const scores:RecommendationItem['scores']={schools:null,parks:null,transport:null,ecology:null,safety:null,commute:null,price:null}
      const contributions:RecommendationItem['contributions']={}
      const keys:Record<string,keyof RecommendationItem['scores']>={schools:'schools',parks:'parks',transport:'transport',ecology:'ecology',safety:'safety',work:'commute'}
      for (const component of item.components) {
        const key=keys[component.priority]
        if (key) { scores[key]=score10(component.score); contributions[key]=component.contribution_points/10 }
      }
      return {apartment_id:apartment.id,title:apartment.title,price:apartment.price,
        price_m2:apartment.area > 0 ? apartment.price/apartment.area : 0,predicted_price_m2:null,
        score:score10(item.score),scores,contributions,commute_minutes:item.commute?.estimated_minutes ?? null,
        reasons:item.components.filter(c => c.status === 'available').map(c => c.explanation),
        warnings:[...item.components.filter(c => c.status !== 'available').map(c => c.explanation),
          ...(item.commute?.badge ? [item.commute.badge] : []),
          ...(item.scoring_status === 'partial' ? ['Оценка частичная: не все данные рассчитаны.'] : [])],
        cover_image_url:apartment.photos[0]?.url ?? null}
    })
  }
}
