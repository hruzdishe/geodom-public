import { describe,expect,it } from 'vitest'
import { buildDistrictStats } from './districtStats'
import type { Apartment } from '../types'

function apartment(id:string,district:string,price:number,area:number,score:number|null,photos=0):Apartment {
  return {
    id,title:'Квартира',price,rooms:2,area,floor:3,total_floors:9,address:'Красноярск',
    house_number:'1',latitude:56,longitude:92,
    district:{ id:district,name:district,description:'' },
    description:'',photos:Array.from({length:photos},(_,index) => ({ id:`${id}-${index}`,url:'/x.jpg',order:index,is_cover:index===0 })),
    source:'seed',created_at:'',status:'published',owner_id:null,
    features:{ schools_1km:0,parks_1km:0,kindergartens_1km:0,nearest_school_m:0,nearest_park_m:0,nearest_transport_m:0 },
    development_projects:[],recommendation:{ score,reasons:[],model_version:'demo',ml_available:false }
  }
}

describe('district stats',() => {
  it('keeps all seven districts and calculates medians from loaded inventory',() => {
    const stats=buildDistrictStats([
      apartment('1','Советский',6_000_000,50,80,1),
      apartment('2','Советский',8_000_000,60,9,0),
      apartment('3','Центральный',10_000_000,70,7.5,2)
    ])

    expect(stats).toHaveLength(7)
    const sovetsky=stats.find(item => item.name === 'Советский')!
    expect(sovetsky.count).toBe(2)
    expect(sovetsky.medianPrice).toBe(7_000_000)
    expect(Math.round(sovetsky.medianPriceM2!)).toBe(126667)
    expect(sovetsky.medianArea).toBe(55)
    expect(sovetsky.averageScore).toBeCloseTo(8.5)
    expect(sovetsky.photoCoverage).toBe(.5)
  })

  it('returns null metrics for districts without inventory',() => {
    const stats=buildDistrictStats([])
    expect(stats.every(item => item.count === 0)).toBe(true)
    expect(stats.every(item => item.medianPrice === null)).toBe(true)
  })
})
