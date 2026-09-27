import { validCoordinate } from './dataSanitizers'

export const COMMUTE_SPEED_KMH=30
export function estimateCommuteMinutes(lat:number|null,lon:number|null,work:{lat:number;lon:number}|null):number|null {
  const home=validCoordinate(lat,lon)
  if (!home || !work || !validCoordinate(work.lat,work.lon)) return null
  const rad=Math.PI/180
  const dLat=(work.lat-home.lat)*rad
  const dLon=(work.lon-home.lon)*rad
  const a=Math.sin(dLat/2)**2+Math.cos(home.lat*rad)*Math.cos(work.lat*rad)*Math.sin(dLon/2)**2
  const km=6371.0088*2*Math.asin(Math.sqrt(Math.min(1,Math.max(0,a))))
  return km/COMMUTE_SPEED_KMH*60
}
