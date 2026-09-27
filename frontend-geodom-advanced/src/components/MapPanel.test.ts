import {expect,it} from 'vitest'
import {normalizeGeoObject} from '../lib/dataSanitizers'
import {classifyGeoObject} from './MapPanel'

it('keeps parking in its own layer rather than treating it as a park',()=>{
 for (const [category,subcategory,layer] of [['parking','parking','parking'],['education','school','education'],['green','park','parks'],['transport','bus_stop','transport']]) {
  const object=normalizeGeoObject({osm_id:1,category,subcategory,lat:56,lon:92})
  expect(object).not.toBeNull()
  expect(classifyGeoObject(object!)).toBe(layer)
 }
})
