// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import { defaultCatalogFilters, defaultPreferences } from '../lib/preferences'
import { useGeoDomStore } from './useGeoDomStore'

beforeEach(() => {
  localStorage.clear()
  useGeoDomStore.setState({
    preferences:defaultPreferences,
    filters:defaultCatalogFilters,
    filtersOpen:false,
    workPicking:false,
    savedIds:[],
    comparedIds:[],
    user:null
  })
})

it('persists catalog filters through the existing storage contract', () => {
  useGeoDomStore.getState().setFilter('district','Советский')
  useGeoDomStore.getState().setFilter('maxPrice',7654321)

  expect(useGeoDomStore.getState().filters).toMatchObject({
    district:'Советский',
    maxPrice:7654321
  })
  expect(JSON.parse(localStorage.getItem('geodom-catalog-filters-v1') || '{}')).toMatchObject({
    district:'Советский',
    maxPrice:7654321
  })
})

it('persists workplace preferences and exits picking mode', () => {
  useGeoDomStore.getState().setWorkPicking(true)
  useGeoDomStore.getState().setWorkLocation({ lat:56.01,lon:92.87 })

  expect(useGeoDomStore.getState().workPicking).toBe(false)
  expect(useGeoDomStore.getState().preferences.work_location).toEqual({ lat:56.01,lon:92.87 })
})

it('keeps at most three apartments in comparison', () => {
  const store = useGeoDomStore.getState()
  store.toggleCompared('a1')
  store.toggleCompared('a2')
  store.toggleCompared('a3')
  store.toggleCompared('a4')

  expect(useGeoDomStore.getState().comparedIds).toEqual(['a1','a2','a3'])
  expect(JSON.parse(localStorage.getItem('geodom-compare-apartments-v1') || '[]')).toEqual(['a1','a2','a3'])

  useGeoDomStore.getState().toggleCompared('a2')
  expect(useGeoDomStore.getState().comparedIds).toEqual(['a1','a3'])
})


it('prunes comparison ids that no longer exist in the active recommendation set', () => {
  useGeoDomStore.getState().toggleCompared('a1')
  useGeoDomStore.getState().toggleCompared('a2')
  useGeoDomStore.getState().toggleCompared('old')

  useGeoDomStore.getState().pruneCompared(['a1','a2','a3'])

  expect(useGeoDomStore.getState().comparedIds).toEqual(['a1','a2'])
})


it('restores a complete saved filter snapshot',() => {
  const snapshot={...defaultCatalogFilters,district:'Октябрьский',rooms:3,minArea:70,onlyWithPhotos:true}
  useGeoDomStore.getState().replaceFilters(snapshot)

  expect(useGeoDomStore.getState().filters).toEqual(snapshot)
  expect(JSON.parse(localStorage.getItem('geodom-catalog-filters-v1') || '{}')).toEqual(snapshot)
})
