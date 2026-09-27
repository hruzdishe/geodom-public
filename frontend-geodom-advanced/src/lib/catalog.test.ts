import { describe,expect,it } from 'vitest'
import { filterApartments,validateApartment } from './catalog'
import { defaultCatalogFilters } from './preferences'
import type { Apartment } from '../types'

const home=(id:string,district:string,priceValue:number,rooms:number,areaValue:number):Apartment => ({
  id,title:'Квартира',price:priceValue,rooms,area:areaValue,floor:3,total_floors:9,
  address:'Красноярск, улица Ленина, 25',house_number:'25',latitude:56,longitude:92,
  district:{ id:district,name:district,description:'' },description:'',photos:[],
  source:'seed',created_at:'',status:'published',owner_id:null,
  features:{ schools_1km:2,parks_1km:1,kindergartens_1km:2,nearest_school_m:400,nearest_park_m:300,nearest_transport_m:200 },
  development_projects:[],recommendation:{ score:82,reasons:[],model_version:'demo',ml_available:true }
})

describe('catalog filters',() => {
  const homes=[
    { ...home('1','Центральный',8000000,2,54),building_year:2018,building_type:'Монолит',photo_count:4 },
    { ...home('2','Советский',5300000,1,38),building_year:1998,building_type:'Панель',photo_count:0 },
    { ...home('3','Центральный',12000000,4,88),building_year:2022,building_type:'Монолит',photo_count:8 }
  ]

  it('combines district budget rooms and search',() => {
    const filters={ ...defaultCatalogFilters,district:'Центральный',maxPrice:9000000,rooms:2,query:'Ленина' }
    expect(filterApartments(homes,filters).map(item => item.id)).toEqual(['1'])
  })

  it('orders prices ascending and leaves input unchanged',() => {
    const filters={ ...defaultCatalogFilters,sort:'price_asc' as const }
    expect(filterApartments(homes,filters).map(item => item.id)).toEqual(['2','1','3'])
    expect(homes[0].id).toBe('1')
  })

  it('filters real housing facets including photos and 4+ rooms',() => {
    const filters={
      ...defaultCatalogFilters,
      rooms:4,
      minArea:70,
      yearFrom:2020,
      buildingType:'Монолит',
      onlyWithPhotos:true
    }
    expect(filterApartments(homes,filters).map(item => item.id)).toEqual(['3'])
  })
})

describe('listing validation',() => {
  it('rejects impossible area and floor',() => {
    expect(validateApartment({ title:'Студия',address:'Ленина, 25',district_name:'Центральный',price:5000000,area:0,rooms:1,floor:12,total_floors:9,description:'Описание' })).toContain('Площадь должна быть больше нуля')
    expect(validateApartment({ title:'Студия',address:'Ленина, 25',district_name:'Центральный',price:5000000,area:32,rooms:1,floor:12,total_floors:9,description:'Описание' })).toContain('Этаж не может превышать этажность дома')
  })

  it('accepts only one of the seven Krasnoyarsk districts',() => {
    expect(validateApartment({ title:'Студия',address:'Ленина, 25',district_name:'',price:5000000,area:32,rooms:1,floor:3,total_floors:9,description:'' })).toContain('Выберите один из 7 районов Красноярска')
    expect(validateApartment({ title:'Студия',address:'Ленина, 25',district_name:'Советский',price:5000000,area:32,rooms:1,floor:3,total_floors:9,description:'' })).not.toContain('Выберите один из 7 районов Красноярска')
  })
})

describe('room and commute filters together',() => {
 const homes=[0,1,2,3,4,5].map(n=>home(String(n),'Центральный',5_000_000,n,50))
 it.each([[-1,[0]],[1,[1]],[2,[2]],[3,[3]],[4,[4,5]],[0,[0,1,2,3,4,5]]])('filters selection %s', (rooms,expected)=>{
  expect(filterApartments(homes,{...defaultCatalogFilters,rooms:Number(rooms)}).map(x=>x.rooms)).toEqual(expected)
 })
 it('reduces results as the allowed time decreases and excludes unknown coordinates',()=>{
  const nearby={...homes[2],id:'near',latitude:56,longitude:92}
  const far={...nearby,id:'far',latitude:56.1}
  const unknown={...nearby,id:'unknown',latitude:null}
  const prefs={work_location:{lat:56,lon:92},max_commute_minutes:20}
  expect(filterApartments([nearby,far,unknown],{...defaultCatalogFilters,rooms:2},prefs).map(x=>x.id)).toEqual(['near'])
  expect(filterApartments([nearby,far,unknown],defaultCatalogFilters,{...prefs,max_commute_minutes:30}).map(x=>x.id)).toEqual(['near','far'])
  expect(filterApartments([nearby,far,unknown],defaultCatalogFilters,{...prefs,work_location:null})).toHaveLength(3)
 })
})
