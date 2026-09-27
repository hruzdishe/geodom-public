export type MortgageBankOffer = {
  id:string
  bank:string
  program:string
  rateFrom:number|null
  rateTo?:number|null
  minDownPaymentPercent:number|null
  maxAmount:number|null
  maxYears:number|null
  updatedAt:string
  sourceUrl:string
  sourceLabel:string
  notes?:string
}

export const KRASNOYARSK_MORTGAGE_SNAPSHOT_DATE='2026-09-26'

/**
 * Demo snapshot for apartment financing UX.
 *
 * The market changes frequently. Values are intentionally stored with a source
 * and updatedAt instead of pretending they are a live bank API.
 * Rates marked null stay visible in the directory but are excluded from payment calculations.
 */
export const KRASNOYARSK_MORTGAGE_BANKS:MortgageBankOffer[]=[
  { id:'sber',bank:'СберБанк',program:'Вторичное жильё',rateFrom:14.5,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:30,updatedAt:'2026-09-04',sourceLabel:'ЛюдиИпотеки / мониторинг ставок',sourceUrl:'https://ludiipoteki.ru/news/index/section/mortgage/entry/izmenenie-stavok-po-ipoteke-na-4-sentyabrya-2026',notes:'Минимальная ставка зависит от параметров клиента и сделки.' },
  { id:'tbank',bank:'Т-Банк',program:'Вторичное жильё',rateFrom:16.9,minDownPaymentPercent:20,maxAmount:50_000_000,maxYears:30,updatedAt:'2026-09-26',sourceLabel:'Банки.ру / Т-Банк',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/bank/tcs/' },
  { id:'kuban',bank:'Кубань Кредит',program:'Ипотека на вторичном рынке',rateFrom:16.5,rateTo:19.2,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:30,updatedAt:'2026-08-31',sourceLabel:'Банки.ру / Кубань Кредит',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/bank/kubankredit/' },
  { id:'primsoc',bank:'Примсоцбанк',program:'Квартира',rateFrom:15.85,rateTo:17.3,minDownPaymentPercent:20.1,maxAmount:50_000_000,maxYears:25,updatedAt:'2026-09-01',sourceLabel:'БанкИнформСервис',sourceUrl:'https://bankinform.ru/services/credits/3881/10' },
  { id:'psb',bank:'ПСБ',program:'Вторичный рынок',rateFrom:17.45,minDownPaymentPercent:20.01,maxAmount:25_000_000,maxYears:30,updatedAt:'2026-08-17',sourceLabel:'ПСБ',sourceUrl:'https://www.psbank.ru/bank/press/news/2026/08/17-01',notes:'Лимит 25 млн ₽ указан для регионов вне Москвы/СПб/МО/ЛО/Краснодарского края.' },
  { id:'khmb',bank:'Хакасский муниципальный банк',program:'Ипотечный плюс',rateFrom:17.5,rateTo:18,minDownPaymentPercent:20.1,maxAmount:null,maxYears:30,updatedAt:'2026-08-05',sourceLabel:'Хакасский муниципальный банк',sourceUrl:'https://kbhmb.ru/private-person/mortgage/ipotechnyj-plyus',notes:'Минимальная ставка связана с условиями банка, включая зарплатный/пенсионный статус.' },
  { id:'atb',bank:'Азиатско-Тихоокеанский банк',program:'Готовое жильё',rateFrom:16.49,rateTo:17.49,minDownPaymentPercent:20.1,maxAmount:50_000_000,maxYears:30,updatedAt:'2026-09-11',sourceLabel:'БанкИнформСервис',sourceUrl:'https://bankinform.ru/services/credits/kredit-v-aziatsko-tihookeanskiy-bank' },
  { id:'akcept',bank:'Банк Акцепт',program:'Жильё на вторичном рынке',rateFrom:17.8,rateTo:18.8,minDownPaymentPercent:20.1,maxAmount:30_000_000,maxYears:30,updatedAt:'2026-09-11',sourceLabel:'Банки.ру',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/city/krasnoyarsk/' },
  { id:'alfa',bank:'Альфа-Банк',program:'На вторичное жильё',rateFrom:17.69,rateTo:19.09,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:30,updatedAt:'2026-09-11',sourceLabel:'Банки.ру',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/city/krasnoyarsk/' },
  { id:'levoberezhny',bank:'Банк «Левобережный»',program:'Вторичное жильё',rateFrom:18,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:25,updatedAt:'2026-09-15',sourceLabel:'Финуслуги',sourceUrl:'https://finuslugi.ru/ipoteka/levoberezhnyj_vtorichnoe_zhile' },
  { id:'vbrr',bank:'ВБРР',program:'Готовое жильё — квартира',rateFrom:17.9,rateTo:18.9,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:30,updatedAt:'2026-09-02',sourceLabel:'Финуслуги',sourceUrl:'https://finuslugi.ru/ipoteka/vbrr_ipoteka_gotovoe_zhile',notes:'Ставка зависит от размера первоначального взноса и дополнительных условий.' },
  { id:'uralsib',bank:'Уралсиб',program:'Вторичное жильё',rateFrom:18.19,minDownPaymentPercent:20,maxAmount:40_000_000,maxYears:30,updatedAt:'2026-09-17',sourceLabel:'СИА / Уралсиб',sourceUrl:'https://uralsib.ru/ipoteka/vtorichnoe-zhile' },
  { id:'sovcom',bank:'Совкомбанк',program:'Вторичное жильё',rateFrom:19.49,minDownPaymentPercent:15,maxAmount:50_000_000,maxYears:30,updatedAt:'2026-09-26',sourceLabel:'Совкомбанк',sourceUrl:'https://sovcombank.ru/articles/novosti-kompanii/sovkombank-snizhaet-protsentnuyu-stavku-po-rinochnim-ipotechnim-programmam',notes:'Для вторички текущая публичная ставка начинается от 18,49% при взносе свыше 50%; при меньшем взносе в публичных условиях встречается 19,49%. Для расчёта используем 19,49% как более типичный сценарий и просим проверить индивидуальные условия.' },
  { id:'sdm',bank:'СДМ-Банк',program:'Ипотечный кредит',rateFrom:18.4,minDownPaymentPercent:30,maxAmount:30_000_000,maxYears:30,updatedAt:'2026-09-11',sourceLabel:'Банки.ру',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/city/krasnoyarsk/' },
  { id:'metallinvest',bank:'Металлинвестбанк',program:'На приобретение готовой недвижимости',rateFrom:17.5,minDownPaymentPercent:20.1,maxAmount:null,maxYears:30,updatedAt:'2026-09-01',sourceLabel:'Frank RG / Банки.ру',sourceUrl:'https://frankrg.com/data-hub/category/mortgage/chart/29612',notes:'Минимальная ставка из мониторинга; финальные региональные условия нужно подтвердить в банке.' },
  { id:'ingo',bank:'Инго Банк',program:'Готовое жильё',rateFrom:20.5,minDownPaymentPercent:30,maxAmount:30_000_000,maxYears:30,updatedAt:'2026-09-16',sourceLabel:'СИА / Инго Банк',sourceUrl:'https://sia.ru/index.php?action=creditinfo&credit=21728&section=3738' },
  { id:'bzhf',bank:'Банк Жилищного Финансирования',program:'Вторичное жильё',rateFrom:20.99,minDownPaymentPercent:40,maxAmount:30_000_000,maxYears:null,updatedAt:'2026-09-11',sourceLabel:'Банки.ру / БЖФ',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/city/krasnoyarsk/' },
  { id:'vtb',bank:'ВТБ',program:'Вторичное жильё',rateFrom:18,minDownPaymentPercent:20.1,maxAmount:100_000_000,maxYears:30,updatedAt:'2026-09-26',sourceLabel:'ВТБ',sourceUrl:'https://www.vtb.ru/personal/ipoteka/vtorichnoe-zhile/' },
  { id:'domrf',bank:'Банк ДОМ.РФ',program:'Вторичное жильё / программы банка',rateFrom:null,minDownPaymentPercent:null,maxAmount:null,maxYears:null,updatedAt:'2026-09-11',sourceLabel:'Банки.ру',sourceUrl:'https://www.banki.ru/products/hypothec/catalogue/ipoteka_na_kvartiru_na_vtorichnom_ryinke/city/krasnoyarsk/',notes:'В городском каталоге есть предложения банка, но найденный snapshot не даёт универсальную рыночную ставку для обычной вторички без специальных условий.' }
]

export function mortgageOfferEligibility(offer:MortgageBankOffer,price:number,downPayment:number,years:number) {
  const downPercent=price > 0 ? downPayment/price*100 : 0
  const principal=Math.max(0,price-downPayment)
  const reasons:string[]=[]
  if (offer.rateFrom === null) reasons.push('Нет расчётной ставки в snapshot')
  if (offer.minDownPaymentPercent !== null && downPercent+1e-6 < offer.minDownPaymentPercent) reasons.push(`Нужен взнос от ${offer.minDownPaymentPercent}%`)
  if (offer.maxAmount !== null && principal > offer.maxAmount) reasons.push('Сумма кредита выше лимита')
  if (offer.maxYears !== null && years > offer.maxYears) reasons.push(`Срок до ${offer.maxYears} лет`)
  return { eligible:reasons.length === 0,reasons }
}
