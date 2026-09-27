// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import {
  defaultCatalogFilters,
  defaultPreferences,
  loadCatalogFilters,
  loadPreferences,
  saveCatalogFilters,
  savePreferences,
  validatePreferences
} from './preferences'

beforeEach(() => localStorage.clear())

it('restores saved inputs including a map-picked workplace and ignores invalid stored data', () => {
  expect(loadPreferences()).toEqual(defaultPreferences)
  savePreferences({
    ...defaultPreferences,
    budget_max:9000000,
    work_location:{ lat:56.01, lon:92.87 },
    priorities:{ ...defaultPreferences.priorities,parks:5 }
  })
  expect(loadPreferences().priorities.parks).toBe(5)
  expect(loadPreferences().budget_max).toBe(9000000)
  expect(loadPreferences().work_location).toEqual({ lat:56.01, lon:92.87 })
  localStorage.setItem('geodom-recommendation-preferences-v1','{broken')
  expect(loadPreferences()).toEqual(defaultPreferences)
})

it('restores catalog filters after a reload', () => {
  expect(loadCatalogFilters()).toEqual(defaultCatalogFilters)
  saveCatalogFilters({ ...defaultCatalogFilters,district:'Советский',rooms:2,maxPrice:8000000 })
  expect(loadCatalogFilters()).toMatchObject({ district:'Советский',rooms:2,maxPrice:8000000 })
})

it('rejects a down payment higher than the budget', () => {
  expect(validatePreferences({ ...defaultPreferences,budget_max:5000000,down_payment:6000000 })).toMatch(/взнос/)
})
