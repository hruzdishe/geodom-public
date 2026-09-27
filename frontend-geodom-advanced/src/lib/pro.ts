import type { Apartment } from '../types'

export type ProLeadIntent='buy'|'rent'

export type ProLead={
  id:string
  name:string
  intent:ProLeadIntent
  budgetMax:number
  monthlyRentMax?:number
  districts:string[]
  roomsMin:number
  roomsMax:number
  maxCommuteMinutes:number
  priorities:string[]
  workLabel:string
  createdAt:string
  consentToContact:boolean
  contact:string
  source:'demo'|'local'|'backend'
}

export const DEMO_PRO_LEADS:ProLead[]=[
  { id:'lead-ivan',name:'Иван',intent:'rent',budgetMax:0,monthlyRentMax:40_000,districts:['Центральный','Железнодорожный'],roomsMin:1,roomsMax:2,maxCommuteMinutes:30,priorities:['Парк для собаки','Работа ≤ 30 мин','Транспорт'],workLabel:'Центр Красноярска',createdAt:'2026-09-26T08:30:00+07:00',consentToContact:true,contact:'+7 900 000-10-01',source:'demo' },
  { id:'lead-anna',name:'Анна',intent:'buy',budgetMax:8_000_000,districts:['Советский','Центральный'],roomsMin:2,roomsMax:3,maxCommuteMinutes:35,priorities:['Школа','Детский сад','Новый дом'],workLabel:'Взлётка',createdAt:'2026-09-26T07:15:00+07:00',consentToContact:true,contact:'+7 900 000-10-02',source:'demo' },
  { id:'lead-mikhail',name:'Михаил',intent:'buy',budgetMax:6_500_000,districts:['Свердловский','Кировский'],roomsMin:1,roomsMax:2,maxCommuteMinutes:45,priorities:['Транспорт','Цена','Парк'],workLabel:'Правый берег',createdAt:'2026-09-25T18:40:00+07:00',consentToContact:true,contact:'+7 900 000-10-03',source:'demo' },
  { id:'lead-elena',name:'Елена',intent:'buy',budgetMax:12_000_000,districts:['Октябрьский','Центральный'],roomsMin:3,roomsMax:4,maxCommuteMinutes:30,priorities:['Школа','Парк','Экология'],workLabel:'Центр',createdAt:'2026-09-25T15:10:00+07:00',consentToContact:false,contact:'+7 900 000-10-04',source:'demo' },
  { id:'lead-alexey',name:'Алексей',intent:'buy',budgetMax:9_500_000,districts:['Советский'],roomsMin:2,roomsMax:3,maxCommuteMinutes:25,priorities:['Работа ≤ 25 мин','Спорт','Транспорт'],workLabel:'Северный',createdAt:'2026-09-25T12:20:00+07:00',consentToContact:true,contact:'+7 900 000-10-05',source:'demo' },
  { id:'lead-olga',name:'Ольга',intent:'rent',budgetMax:0,monthlyRentMax:55_000,districts:['Центральный','Октябрьский'],roomsMin:2,roomsMax:3,maxCommuteMinutes:30,priorities:['Парк','Тишина','Кафе'],workLabel:'Исторический центр',createdAt:'2026-09-24T19:30:00+07:00',consentToContact:true,contact:'+7 900 000-10-06',source:'demo' }
]

export type LeadMatch={
  lead:ProLead
  score:number
  reasons:string[]
}

export function matchLeadToApartment(lead:ProLead,apartment:Apartment):LeadMatch {
  const reasons:string[]=[]
  let score=0
  let weight=0

  if (lead.intent !== 'buy') return { lead,score:0,reasons:['Лид ищет аренду, объявление — продажа'] }

  weight+=35
  if (apartment.price <= lead.budgetMax) { score+=35;reasons.push('Входит в бюджет') }

  weight+=25
  if (lead.districts.includes(apartment.district.name)) { score+=25;reasons.push('Подходящий район') }

  weight+=20
  if (apartment.rooms >= lead.roomsMin && apartment.rooms <= lead.roomsMax) { score+=20;reasons.push('Подходит комнатность') }

  weight+=20
  const priorityText=lead.priorities.join(' ').toLocaleLowerCase('ru')
  if (priorityText.includes('парк') && (apartment.features.parks_1km ?? 0) > 0) { score+=7;reasons.push('Есть парк рядом') }
  if (priorityText.includes('школ') && (apartment.features.schools_1km ?? 0) > 0) { score+=7;reasons.push('Есть школы рядом') }
  if (priorityText.includes('транспорт') && apartment.features.nearest_transport_m !== null && apartment.features.nearest_transport_m <= 500) { score+=6;reasons.push('Транспорт рядом') }

  return { lead,score:Math.round(score/weight*100),reasons }
}

const promotionKey='geodom-pro-promoted-v1'

export function loadPromotedIds():string[] {
  try {
    const parsed=JSON.parse(localStorage.getItem(promotionKey) || '[]')
    return Array.isArray(parsed) ? parsed.filter(value => typeof value === 'string') : []
  } catch {
    return []
  }
}

export function savePromotedIds(ids:string[]) {
  localStorage.setItem(promotionKey,JSON.stringify([...new Set(ids)]))
}

export function leadAnalytics(leads:ProLead[]) {
  const buy=leads.filter(lead => lead.intent === 'buy')
  const districtCounts=new Map<string,number>()
  const priorityCounts=new Map<string,number>()
  for (const lead of leads) {
    for (const district of lead.districts) districtCounts.set(district,(districtCounts.get(district) || 0)+1)
    for (const priority of lead.priorities) priorityCounts.set(priority,(priorityCounts.get(priority) || 0)+1)
  }
  const budgets=buy.map(lead => lead.budgetMax).filter(Boolean).sort((a,b) => a-b)
  const medianBudget=budgets.length ? budgets[Math.floor(budgets.length/2)] : 0
  return {
    leads:leads.length,
    buyLeads:buy.length,
    rentLeads:leads.length-buy.length,
    medianBudget,
    topDistricts:[...districtCounts.entries()].sort((a,b) => b[1]-a[1]).slice(0,4),
    topPriorities:[...priorityCounts.entries()].sort((a,b) => b[1]-a[1]).slice(0,5)
  }
}


export type LeadStage='new'|'contacted'|'viewing'|'won'|'lost'

const leadPipelineKey='geodom-pro-lead-pipeline-v1'

export function loadLeadPipeline():Record<string,LeadStage> {
  try {
    const parsed=JSON.parse(localStorage.getItem(leadPipelineKey) || '{}') as Record<string,unknown>
    const allowed=new Set<LeadStage>(['new','contacted','viewing','won','lost'])
    return Object.fromEntries(Object.entries(parsed).filter((entry):entry is [string,LeadStage] => allowed.has(entry[1] as LeadStage)))
  } catch {
    return {}
  }
}

export function setLeadStage(leadId:string,stage:LeadStage) {
  const pipeline={...loadLeadPipeline(),[leadId]:stage}
  localStorage.setItem(leadPipelineKey,JSON.stringify(pipeline))
  return pipeline
}

export function clearLeadStage(leadId:string) {
  const pipeline=loadLeadPipeline()
  delete pipeline[leadId]
  localStorage.setItem(leadPipelineKey,JSON.stringify(pipeline))
  return pipeline
}

export const proLeadPipelineStorageKey=leadPipelineKey
