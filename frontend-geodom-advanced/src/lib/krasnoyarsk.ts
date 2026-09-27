export const KRASNOYARSK_DISTRICTS = [
  { id:'zheleznodorozhny',name:'Железнодорожный' },
  { id:'kirovsky',name:'Кировский' },
  { id:'leninsky',name:'Ленинский' },
  { id:'oktyabrsky',name:'Октябрьский' },
  { id:'sverdlovsky',name:'Свердловский' },
  { id:'sovetsky',name:'Советский' },
  { id:'centralny',name:'Центральный' }
] as const

export type KrasnoyarskDistrictName = typeof KRASNOYARSK_DISTRICTS[number]['name']

export function isKrasnoyarskDistrict(value:string):value is KrasnoyarskDistrictName {
  return KRASNOYARSK_DISTRICTS.some(district => district.name === value)
}
