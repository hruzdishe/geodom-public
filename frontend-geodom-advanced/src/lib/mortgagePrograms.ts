export type MortgageProgramId='market'|'family'|'it'|'far-east'|'custom'

export type MortgageProgramContext={
  childrenCount:number
  youngestChildAge:number|null
  apartmentArea?:number
  now?:Date
}

export type MortgageProgramTerms={
  id:MortgageProgramId
  title:string
  shortTitle:string
  rate:number|null
  minDownPaymentPercent:number|null
  maxAmount:number|null
  maxYears:number|null
  available:boolean
  badge:string
  description:string
  warning?:string
  sourceUrl?:string
}

const FAMILY_RULE_CHANGE='2026-10-01T00:00:00+03:00'

function familyTerms(context:MortgageProgramContext):MortgageProgramTerms {
  const now=context.now ?? new Date()
  const afterChange=now.getTime() >= new Date(FAMILY_RULE_CHANGE).getTime()

  if (!afterChange) {
    return {
      id:'family',
      title:'Семейная ипотека',
      shortTitle:'Семейная',
      rate:6,
      minDownPaymentPercent:20,
      maxAmount:6_000_000,
      maxYears:30,
      available:true,
      badge:'до 6%',
      description:'Льготная программа для семей с детьми. Для Красноярского края базовый лимит льготной части — до 6 млн ₽.',
      warning:'Обычная вторичка подходит не всегда: программа в основном рассчитана на первичный рынок, ИЖС и отдельные случаи вторичного жилья. С 1 октября 2026 условия программы меняются.',
      sourceUrl:'https://xn--d1aqf.xn--p1ai/mortgage/family-mortgage/'
    }
  }

  const children=Math.max(0,Math.floor(context.childrenCount))
  const youngest=context.youngestChildAge
  const hasYoungChild=youngest !== null && youngest <= 6

  if (!hasYoungChild || children < 1) {
    return {
      id:'family',
      title:'Семейная ипотека',
      shortTitle:'Семейная',
      rate:null,
      minDownPaymentPercent:20,
      maxAmount:null,
      maxYears:15,
      available:false,
      badge:'с 01.10.2026',
      description:'Для расчёта по новым условиям укажите количество детей и возраст младшего ребёнка.',
      warning:'С 1 октября 2026 для новых кредитов в регионах вне Москвы/МО/СПб/ЛО ставка и лимит зависят от количества детей; как минимум один ребёнок должен быть младше 7 лет.',
      sourceUrl:'https://www.consultant.ru/law/hotdocs/95745.html'
    }
  }

  const tier=children >= 5
    ? { rate:2,maxAmount:10_000_000 }
    : children === 4
      ? { rate:4,maxAmount:10_000_000 }
      : children === 3
        ? { rate:6,maxAmount:10_000_000 }
        : children === 2
          ? { rate:8,maxAmount:8_000_000 }
          : { rate:10,maxAmount:6_000_000 }

  return {
    id:'family',
    title:'Семейная ипотека',
    shortTitle:'Семейная',
    rate:tier.rate,
    minDownPaymentPercent:20,
    maxAmount:tier.maxAmount,
    maxYears:15,
    available:true,
    badge:`${tier.rate}%`,
    description:`Новые условия с 1 октября 2026: ${children} ${children === 1 ? 'ребёнок' : children < 5 ? 'ребёнка' : 'детей'} → ставка ${tier.rate}% и льготный лимит до ${Math.round(tier.maxAmount/1_000_000)} млн ₽.`,
    warning:'Калькулятор считает льготную часть. Фактическая доступность зависит от состава семьи, объекта, банка и требований программы.',
    sourceUrl:'https://www.consultant.ru/law/hotdocs/95745.html'
  }
}

export function resolveMortgageProgram(id:MortgageProgramId,context:MortgageProgramContext):MortgageProgramTerms {
  if (id === 'family') return familyTerms(context)
  if (id === 'it') return {
    id,
    title:'IT-ипотека',
    shortTitle:'IT',
    rate:6,
    minDownPaymentPercent:20,
    maxAmount:9_000_000,
    maxYears:30,
    available:true,
    badge:'до 6%',
    description:'Для сотрудников аккредитованных IT-компаний. Льготная сумма — до 9 млн ₽.',
    warning:'Обычная вторичка в программу не входит. Нужно проверить работодателя, регион, доход и тип приобретаемого жилья.',
    sourceUrl:'https://xn--d1aqf.xn--p1ai/mortgage/it-mortgage/'
  }
  if (id === 'far-east') return {
    id,
    title:'Дальневосточная и арктическая',
    shortTitle:'ДФО / Арктика',
    rate:2,
    minDownPaymentPercent:20,
    maxAmount:context.apartmentArea && context.apartmentArea >= 60 ? 9_000_000 : 6_000_000,
    maxYears:20,
    available:false,
    badge:'до 2%',
    description:'Льготная ипотека для жилья на Дальнем Востоке и сухопутных территориях Арктической зоны.',
    warning:'Для квартиры в Красноярске эта программа недоступна. Оставляем её в интерфейсе, чтобы архитектура калькулятора поддерживала другие регионы.',
    sourceUrl:'https://government.ru/sanctions_measures/measure/170/'
  }
  if (id === 'custom') return {
    id,
    title:'Своя ставка',
    shortTitle:'Своя ставка',
    rate:null,
    minDownPaymentPercent:null,
    maxAmount:null,
    maxYears:null,
    available:true,
    badge:'ручной расчёт',
    description:'Введите индивидуальную ставку из предложения банка.',
  }
  return {
    id:'market',
    title:'Рыночная ипотека',
    shortTitle:'Рыночная',
    rate:null,
    minDownPaymentPercent:null,
    maxAmount:null,
    maxYears:null,
    available:true,
    badge:'по банкам',
    description:'Сравнение публичного snapshot-а банков Красноярска для вторичного жилья.'
  }
}

export const MORTGAGE_PROGRAM_ORDER:MortgageProgramId[]=['market','family','it','far-east','custom']

export function mortgageProgramEligibility(terms:MortgageProgramTerms,price:number,downPayment:number,years:number) {
  const principal=Math.max(0,price-downPayment)
  const downPercent=price > 0 ? downPayment/price*100 : 0
  const reasons:string[]=[]
  if (!terms.available) reasons.push(terms.warning || 'Программа недоступна для текущего объекта')
  if (terms.minDownPaymentPercent !== null && downPercent+1e-6 < terms.minDownPaymentPercent) reasons.push(`Первоначальный взнос от ${terms.minDownPaymentPercent}%`)
  if (terms.maxAmount !== null && principal > terms.maxAmount) reasons.push(`Льготная сумма до ${Math.round(terms.maxAmount/1_000_000)} млн ₽`)
  if (terms.maxYears !== null && years > terms.maxYears) reasons.push(`Максимальный срок ${terms.maxYears} лет`)
  return { eligible:reasons.length === 0,reasons,principal,downPercent }
}
