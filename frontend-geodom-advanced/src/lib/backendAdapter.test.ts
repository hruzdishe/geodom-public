import {describe,it,expect} from 'vitest'
import {backendListingPayload,backendRecommendationPayload,mapBackendApartment,mapBackendRecommendation,type BackendApartment,type BackendRecommendationResponse} from './backendAdapter'
import {defaultPreferences,defaultCatalogFilters} from './preferences'
const home:BackendApartment={id:1,title:'Квартира',price:'8700000.00',area:'50.00',rooms:0,floor:3,total_floors:9,address:'Красноярск',district:{id:1,name:'Центральный',center_latitude:null,center_longitude:null},status:'published',created_at:'2026-09-27',deal_type:'sale',rent_period:null,features:{schools_1km:0,parks_1km:null,nearest_school_m:'125.5'},photos:[{id:1,url:'http://minio/photo?signature=keep',position:0,is_cover:false},{id:2,url:'http://minio/cover?signature=keep',position:1,is_cover:true}]}

describe('FastAPI DTO adapters',()=>{
  it('preserves zero versus null, numeric decimals, cover and missing coordinates',()=>{
    const result=mapBackendApartment(home)
    expect(result.price).toBe(8700000);expect(result.rooms).toBe(0)
    expect(result.latitude).toBeNull();expect(result.longitude).toBeNull()
    expect(result.features).toMatchObject({schools_1km:0,parks_1km:null,nearest_school_m:125.5})
    expect(result.photos[0].url).toBe('http://minio/cover?signature=keep')
  })
  it('scales even small backend scores exactly once and preserves missing scores',()=>{
    const raw:BackendRecommendationResponse={request_id:'r',model_version:'explainable_heuristic_v1',scoring_version:'apartment_scoring_v1',fallback_used:false,status:'ok',eligible_count:1,returned_count:1,limitations:[],unsupported_priorities:[],items:[{rank:1,apartment:home,score:8,score_coverage:1,scoring_status:'complete',commute:null,components:[{priority:'schools',score:80,contribution_points:8,status:'available',explanation:'Школа рядом'}]}]}
    const result=mapBackendRecommendation(raw)
    expect(result.items[0]).toMatchObject({score:0.8,scores:{schools:8},contributions:{schools:0.8},reasons:['Школа рядом']})
    raw.items[0].score=null
    expect(mapBackendRecommendation(raw).items[0].score).toBeNull()
  })
  it('sends only supported request fields',()=>{
    const payload=backendRecommendationPayload(defaultPreferences)
    expect(payload.price_max).toBe(defaultPreferences.budget_max)
    expect(payload).not.toHaveProperty('down_payment')
    expect(backendListingPayload({title:'Дом',address:'Красноярск',district_name:'Центральный',price:1,area:1,rooms:0,floor:1,total_floors:1,description:''})).toMatchObject({deal_type:'sale',rent_period:null})
  })
})

it.each([[0,[]],[-1,[0]],[1,[1]],[2,[2]],[3,[3]],[4,Array.from({length:17},(_,i)=>i+4)]])('passes room selection %s before ranking', (rooms,expected) => {
 const payload=backendRecommendationPayload({...defaultPreferences,catalog_filters:{...defaultCatalogFilters,rooms:Number(rooms),district:'Советский'},work_location:{lat:56,lon:92},max_commute_minutes:20})
 expect(payload.rooms).toEqual(expected)
 expect(payload.districts).toEqual(['Советский'])
 expect(payload.work).toEqual({lat:56,lon:92,max_minutes:20})
})
