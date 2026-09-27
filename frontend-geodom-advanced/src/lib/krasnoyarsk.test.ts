import { describe,expect,it } from 'vitest'
import { KRASNOYARSK_DISTRICTS,isKrasnoyarskDistrict } from './krasnoyarsk'

describe('Krasnoyarsk districts',() => {
  it('contains all seven administrative districts exactly once',() => {
    expect(KRASNOYARSK_DISTRICTS.map(item => item.name)).toEqual([
      'Железнодорожный',
      'Кировский',
      'Ленинский',
      'Октябрьский',
      'Свердловский',
      'Советский',
      'Центральный'
    ])
    expect(new Set(KRASNOYARSK_DISTRICTS.map(item => item.name)).size).toBe(7)
  })

  it('validates district names',() => {
    expect(isKrasnoyarskDistrict('Советский')).toBe(true)
    expect(isKrasnoyarskDistrict('Уточняется')).toBe(false)
  })
})
