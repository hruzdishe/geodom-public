// @vitest-environment jsdom
import { expect, it } from 'vitest'
import { cleanText, finiteNumber, normalizeGeoObjects, parseWktPoint } from './dataSanitizers'

it('treats NaN-like and empty parquet values as missing data', () => {
  expect(cleanText(' NaN ')).toBeNull()
  expect(cleanText('')).toBeNull()
  expect(finiteNumber(Number.NaN)).toBeNull()
  expect(finiteNumber('')).toBeNull()
})

it('parses parquet WKT points using lon lat order', () => {
  expect(parseWktPoint('POINT (92.6464961 56.0247489)')).toEqual({ lat:56.0247489, lon:92.6464961 })
  expect(parseWktPoint('POINT (oops)')).toBeNull()
})

it('drops rows without valid geometry and keeps missing optional fields as null', () => {
  const rows = normalizeGeoObjects([
    {
      osm_id:'osm:node/1',
      osm_type:'node',
      category:'education',
      subcategory:'university',
      name:'   ',
      location_label:'СФУ',
      address:'nan',
      geometry:'POINT (92.77 55.99)',
      source:'openstreetmap',
      source_url:'https://www.openstreetmap.org/node/1',
      address_distance_m:Number.NaN,
      address_is_approximate:'false'
    },
    { osm_id:'osm:node/2', geometry:'', category:'transport' }
  ])
  expect(rows).toHaveLength(1)
  expect(rows[0]).toMatchObject({
    id:'osm:node/1',
    name:'СФУ',
    address:null,
    lat:55.99,
    lon:92.77,
    addressDistanceM:null,
    addressIsApproximate:false
  })
})


it('accepts API wrappers and direct coordinates in addition to parquet WKT', () => {
  const rows = normalizeGeoObjects({
    items:[
      { osm_id:'osm:node/3', category:'transport', name:'Остановка', lat:'56.01', lon:'92.87' },
      { osm_id:'osm:node/4', category:'education', name:'Школа', geometry:{ type:'Point',coordinates:[92.90,56.04] } }
    ]
  })
  expect(rows).toHaveLength(2)
  expect(rows[0]).toMatchObject({ lat:56.01,lon:92.87 })
  expect(rows[1]).toMatchObject({ lat:56.04,lon:92.90 })
})
