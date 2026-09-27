// @vitest-environment jsdom
import { beforeEach,describe,expect,it } from 'vitest'
import { DEMO_PRO_LEADS,leadAnalytics,loadLeadPipeline,matchLeadToApartment,setLeadStage } from './pro'
import type { Apartment } from '../types'

const apartment:Apartment={
  id:'a',title:'Квартира',price:7_000_000,rooms:2,area:55,floor:5,total_floors:10,address:'Красноярск',house_number:'1',latitude:56,longitude:92,
  district:{ id:'s',name:'Советский',description:'' },description:'',photos:[],source:'seed',created_at:'',status:'published',owner_id:null,
  features:{ schools_1km:2,parks_1km:1,kindergartens_1km:2,nearest_school_m:300,nearest_park_m:400,nearest_transport_m:200 },
  development_projects:[],recommendation:{ score:8,reasons:[],model_version:'demo',ml_available:false }
}

describe('GeoDom Pro demo',() => {
  beforeEach(() => localStorage.clear())
  it('matches a qualified buyer to an apartment',() => {
    const lead=DEMO_PRO_LEADS.find(item => item.id === 'lead-anna')!
    const result=matchLeadToApartment(lead,apartment)
    expect(result.score).toBeGreaterThanOrEqual(80)
    expect(result.reasons).toContain('Входит в бюджет')
    expect(result.reasons).toContain('Подходящий район')
  })

  it('does not match rental demand to a sale listing',() => {
    const lead=DEMO_PRO_LEADS.find(item => item.intent === 'rent')!
    expect(matchLeadToApartment(lead,apartment).score).toBe(0)
  })

  it('aggregates demand without exposing contacts',() => {
    const analytics=leadAnalytics(DEMO_PRO_LEADS)
    expect(analytics.leads).toBe(DEMO_PRO_LEADS.length)
    expect(analytics.medianBudget).toBeGreaterThan(0)
    expect(analytics.topDistricts.length).toBeGreaterThan(0)
  })

  it('persists CRM pipeline stage per lead',() => {
    setLeadStage('lead-anna','contacted')
    setLeadStage('lead-mikhail','viewing')
    expect(loadLeadPipeline()).toEqual({
      'lead-anna':'contacted',
      'lead-mikhail':'viewing'
    })
  })
})
