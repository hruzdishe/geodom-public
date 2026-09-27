// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'
import { api } from './api'
import { readDemoEvents } from './recommendations'

beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
describe('demo listing lifecycle', () => {
  it('registers, signs in, publishes, edits and hides a user-owned listing', async () => {
    const user = await api.register('example_user','password123')
    expect((await api.login('example_user','password123')).id).toBe(user.id)
    const input = { title:'Тестовая квартира', address:'Красноярск, улица Ленина, 25', district_name:'Центральный', price:6000000, area:48, rooms:2, floor:3, total_floors:9, description:'Тест' }
    const created = await api.create(input)
    expect(created.source).toBe('user')
    expect((await api.list()).some(x => x.id === created.id)).toBe(true)
    expect((await api.mine()).map(x => x.id)).toContain(created.id)
    await api.update(created.id,{...input,price:6200000})
    expect((await api.detail(created.id)).price).toBe(6200000)
    await api.hide(created.id)
    expect((await api.list()).some(x => x.id === created.id)).toBe(false)
    expect((await api.mine()).find(x => x.id === created.id)?.status).toBe('hidden')
  })
  it('rejects duplicate login and wrong password', async () => {
    await api.register('first_user','password123')
    await expect(api.register('FIRST_USER','password456')).rejects.toThrow('занят')
    await expect(api.login('first_user','wrongpass')).rejects.toThrow('Неверный')
  })

  it('registers when crypto.randomUUID is unavailable', async () => {
    const original = globalThis.crypto
    Object.defineProperty(globalThis,'crypto',{
      configurable:true,
      value:{ getRandomValues:original.getRandomValues.bind(original) }
    })
    try {
      const user = await api.register('compat_user','password123')
      expect(user.id).toBeTruthy()
      expect((await api.login('compat_user','password123')).id).toBe(user.id)
    } finally {
      Object.defineProperty(globalThis,'crypto',{ configurable:true,value:original })
    }
  })
})

describe('recommendation integration', () => {
  it('returns a request id and records a correlated event', async () => {
    const response = await api.recommend({ budget_max:9000000, down_payment:0, family:{ adults:1, children:0 }, work_location:null, max_commute_minutes:40, priorities:{ schools:3,parks:3,transport:3,ecology:3,safety:3 }, limit:10 })
    await api.event({ request_id:response.request_id,event:'click',entity_type:'apartment',entity_id:response.items[0].apartment_id,position:1 })
    expect(readDemoEvents()[0]).toMatchObject({ request_id:response.request_id,event:'click',position:1 })
  })
})


describe('district analytics', () => {
  it('returns all seven Krasnoyarsk districts in demo mode', async () => {
    const stats = await api.districtStats()
    expect(stats).toHaveLength(7)
    expect(new Set(stats.map(item => item.name)).size).toBe(7)
    expect(stats.some(item => item.count > 0)).toBe(true)
  })
})
