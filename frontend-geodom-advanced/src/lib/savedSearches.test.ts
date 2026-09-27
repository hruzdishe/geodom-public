// @vitest-environment jsdom
import { beforeEach,describe,expect,it } from 'vitest'
import { createSavedSearch,deleteSavedSearch,loadSavedSearches,markSavedSearchSeen,savedSearchNewMatches } from './savedSearches'
import { defaultCatalogFilters,defaultPreferences } from './preferences'
import type { Apartment } from '../types'

function apartment(id:string,district:string,price:number):Apartment {
  return {
    id,title:'Квартира',price,rooms:2,area:50,floor:3,total_floors:9,address:'Красноярск',house_number:'1',latitude:56,longitude:92,
    district:{id:district,name:district,description:''},description:'',photos:[],source:'seed',created_at:'',status:'published',owner_id:null,
    features:{schools_1km:0,parks_1km:0,kindergartens_1km:0,nearest_school_m:0,nearest_park_m:0,nearest_transport_m:0},
    development_projects:[],recommendation:{score:8,reasons:[],model_version:'demo',ml_available:false}
  }
}

beforeEach(() => localStorage.clear())

describe('saved searches',() => {
  it('stores the current matching apartments as seen',() => {
    const items=[apartment('1','Советский',6_000_000),apartment('2','Центральный',9_000_000)]
    const search=createSavedSearch({
      label:'Советский до 7 млн',
      preferences:defaultPreferences,
      filters:{...defaultCatalogFilters,district:'Советский',maxPrice:7_000_000},
      items
    })
    expect(search.seenApartmentIds).toEqual(['1'])
    expect(loadSavedSearches()).toHaveLength(1)
  })

  it('detects new matches and marks them seen',() => {
    const first=[apartment('1','Советский',6_000_000)]
    const search=createSavedSearch({
      label:'Советский',
      preferences:defaultPreferences,
      filters:{...defaultCatalogFilters,district:'Советский'},
      items:first
    })
    const expanded=[...first,apartment('2','Советский',7_000_000)]
    expect(savedSearchNewMatches(search,expanded).map(item => item.id)).toEqual(['2'])
    markSavedSearchSeen(search.id,expanded)
    expect(savedSearchNewMatches(loadSavedSearches()[0],expanded)).toHaveLength(0)
  })

  it('deletes a saved search',() => {
    const search=createSavedSearch({label:'Test',preferences:defaultPreferences,filters:defaultCatalogFilters,items:[]})
    deleteSavedSearch(search.id)
    expect(loadSavedSearches()).toHaveLength(0)
  })
})
