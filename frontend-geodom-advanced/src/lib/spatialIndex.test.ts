import { describe,expect,it } from 'vitest'
import { createSpatialIndex } from './spatialIndex'

type Point = { id:number;lat:number;lon:number }

describe('spatial index',() => {
  it('returns only points inside a padded viewport',() => {
    const points:Point[] = [
      { id:1,lat:56.01,lon:92.87 },
      { id:2,lat:56.02,lon:92.88 },
      { id:3,lat:57.2,lon:95.0 }
    ]
    const index = createSpatialIndex(points,item => item,.01)
    expect(index.query({ minLat:56,maxLat:56.03,minLon:92.85,maxLon:92.9 }).map(x => x.id).sort()).toEqual([1,2])
  })

  it('supports hard limits for render budgets',() => {
    const points = Array.from({ length:50000 },(_,id) => ({
      id,
      lat:56+(id%250)*0.0005,
      lon:92.7+(id%400)*0.0005
    }))
    const index = createSpatialIndex(points,item => item,.01)
    expect(index.size).toBe(50000)
    const visible = index.query({ minLat:55.9,maxLat:56.2,minLon:92.6,maxLon:93.1 },{ limit:320 })
    expect(visible).toHaveLength(320)
  })

  it('returns all indexed values when bounds are unavailable',() => {
    const points:Point[] = [{ id:1,lat:56,lon:92 },{ id:2,lat:57,lon:93 }]
    const index = createSpatialIndex(points,item => item)
    expect(index.query(null).map(x => x.id)).toEqual([1,2])
  })
})
