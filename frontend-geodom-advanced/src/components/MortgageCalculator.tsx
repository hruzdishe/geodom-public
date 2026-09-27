import { useEffect,useMemo,useState } from 'react'
import { ArrowLeft,ArrowRight,ArrowUpRight,Baby,BriefcaseBusiness,Building2,Check,ChevronDown,Landmark,Save,ShieldCheck,Sparkles,UserRound } from 'lucide-react'
import { price as formatPrice } from '../lib/catalog'
import { KRASNOYARSK_MORTGAGE_BANKS,KRASNOYARSK_MORTGAGE_SNAPSHOT_DATE,mortgageOfferEligibility,type MortgageBankOffer } from '../lib/mortgageBanks'
import { mortgageProgramEligibility,resolveMortgageProgram,type MortgageProgramTerms } from '../lib/mortgagePrograms'
import { clearMortgageWizardDraft,loadMortgageWizardDraft,saveMortgageCalculation,saveMortgageWizardDraft } from '../lib/mortgageStorage'

export type MortgageCalculation={ principal:number; monthlyPayment:number; totalPayment:number; overpayment:number }
export type MortgageComparisonTerms={ apartmentPrice:number; downPayment:number; annualRate:number; mortgageYears:number }
export type MortgageWizardScenario='newbuild'|'secondary'|'family'|'it'

export type MortgageWizardOffer={
  offer:MortgageBankOffer
  rate:number|null
  eligible:boolean
  reasons:string[]
  result:MortgageCalculation|null
  programRate:boolean
  estimated:boolean
}

const SCENARIOS:Array<{id:MortgageWizardScenario;title:string;subtitle:string}>=[
  {id:'newbuild',title:'Новостройка',subtitle:'Банки и программы для нового жилья'},
  {id:'secondary',title:'Вторичка',subtitle:'Готовая квартира на вторичном рынке'},
  {id:'family',title:'Семейная ипотека',subtitle:'Льготная программа для семей'},
  {id:'it',title:'IT-ипотека',subtitle:'Для сотрудников аккредитованных IT-компаний'}
]

const BANK_MARKS:Record<string,string>={
  sber:'С',tbank:'Т',alfa:'А',vtb:'ВТБ',domrf:'ДОМ',psb:'ПСБ',sovcom:'СК',
  kuban:'КК',primsoc:'ПС',khmb:'ХМ',atb:'АТБ',akcept:'АК',levoberezhny:'ЛБ',
  vbrr:'ВБ',uralsib:'УР',sdm:'СД',metallinvest:'МИ',ingo:'ИН',bzhf:'БЖ'
}

export function calculateMortgage(price:number,downPayment:number,annualRate:number,years:number):MortgageCalculation {
  const safePrice=Math.max(0,Number.isFinite(price) ? price : 0)
  const safeDown=Math.min(safePrice,Math.max(0,Number.isFinite(downPayment) ? downPayment : 0))
  const principal=Math.max(0,safePrice-safeDown)
  const months=Math.max(1,Math.round((Number.isFinite(years) ? years : 1)*12))
  const monthlyRate=Math.max(0,Number.isFinite(annualRate) ? annualRate : 0)/100/12
  if (!principal) return { principal:0,monthlyPayment:0,totalPayment:0,overpayment:0 }
  const monthlyPayment=monthlyRate === 0 ? principal/months : principal*monthlyRate/-Math.expm1(-months*Math.log1p(monthlyRate))
  const totalPayment=monthlyPayment*months
  return { principal,monthlyPayment,totalPayment,overpayment:Math.max(0,totalPayment-principal) }
}

function scenarioIcon(id:MortgageWizardScenario) {
  if (id === 'newbuild') return <Building2 size={18}/>
  if (id === 'family') return <Baby size={18}/>
  if (id === 'it') return <BriefcaseBusiness size={18}/>
  return <Landmark size={18}/>
}

function scenarioProgram(scenario:MortgageWizardScenario,childrenCount:number,youngestChildAge:number|null,apartmentArea?:number):MortgageProgramTerms {
  if (scenario === 'family') return resolveMortgageProgram('family',{childrenCount,youngestChildAge,apartmentArea})
  if (scenario === 'it') return resolveMortgageProgram('it',{childrenCount,youngestChildAge,apartmentArea})
  return resolveMortgageProgram('market',{childrenCount,youngestChildAge,apartmentArea})
}

export function buildMortgageWizardOffers({
  scenario,
  price,
  downPayment,
  years,
  childrenCount=1,
  youngestChildAge=3,
  apartmentArea
}:{
  scenario:MortgageWizardScenario
  price:number
  downPayment:number
  years:number
  childrenCount?:number
  youngestChildAge?:number|null
  apartmentArea?:number
}):MortgageWizardOffer[] {
  const program=scenarioProgram(scenario,childrenCount,youngestChildAge,apartmentArea)
  const programSpecific=scenario === 'family' || scenario === 'it'

  return KRASNOYARSK_MORTGAGE_BANKS.map(offer => {
    if (programSpecific) {
      const eligibility=mortgageProgramEligibility(program,price,downPayment,years)
      const rate=program.rate
      return {
        offer,
        rate,
        eligible:eligibility.eligible && rate !== null,
        reasons:eligibility.reasons,
        result:eligibility.eligible && rate !== null ? calculateMortgage(price,downPayment,rate,years) : null,
        programRate:true,
        estimated:false
      }
    }

    const eligibility=mortgageOfferEligibility(offer,price,downPayment,years)
    return {
      offer,
      rate:offer.rateFrom,
      eligible:eligibility.eligible && offer.rateFrom !== null,
      reasons:eligibility.reasons,
      result:eligibility.eligible && offer.rateFrom !== null ? calculateMortgage(price,downPayment,offer.rateFrom,years) : null,
      programRate:false,
      estimated:scenario === 'newbuild'
    }
  }).sort((a,b) => {
    if (a.eligible !== b.eligible) return a.eligible ? -1 : 1
    if (a.result && b.result && a.result.monthlyPayment !== b.result.monthlyPayment) return a.result.monthlyPayment-b.result.monthlyPayment
    if (a.rate !== null && b.rate !== null && a.rate !== b.rate) return a.rate-b.rate
    if (a.rate !== null) return -1
    if (b.rate !== null) return 1
    return a.offer.bank.localeCompare(b.offer.bank,'ru')
  })
}

function BankMark({offer,size='normal'}:{offer:MortgageBankOffer;size?:'normal'|'large'}) {
  return <span className={`mortgage-bank-mark mortgage-bank-mark-${offer.id} ${size === 'large' ? 'large' : ''}`} aria-hidden="true">{BANK_MARKS[offer.id] || offer.bank.slice(0,2).toUpperCase()}</span>
}

function clamp(value:number,min:number,max:number) {
  return Math.min(max,Math.max(min,Number.isFinite(value) ? value : min))
}

function scenarioLabel(id:MortgageWizardScenario) {
  return SCENARIOS.find(item => item.id === id)?.title || 'Ипотека'
}

export function MortgageCalculator({ apartmentPrice,apartmentArea,defaultDownPayment=0,onCompareRent }:{
  apartmentPrice:number
  apartmentArea?:number
  defaultDownPayment?:number
  onCompareRent?:(terms:MortgageComparisonTerms) => void
}) {
  const initialPrice=Math.max(300_000,Math.round(apartmentPrice))
  const initialDown=Math.min(initialPrice,defaultDownPayment > 0 ? defaultDownPayment : Math.round(initialPrice*.2))
  const [initialDraft]=useState(() => loadMortgageWizardDraft(initialPrice))

  const [step,setStep]=useState<1|2|3|4>(initialDraft?.step ?? 1)
  const [scenario,setScenario]=useState<MortgageWizardScenario>(initialDraft?.scenario ?? 'secondary')
  const [bankId,setBankId]=useState(initialDraft?.bankId ?? 'sber')
  const [propertyPrice,setPropertyPrice]=useState(initialDraft?.propertyPrice ?? initialPrice)
  const [downPayment,setDownPayment]=useState(Math.min(initialDraft?.downPayment ?? initialDown,initialDraft?.propertyPrice ?? initialPrice))
  const [years,setYears]=useState(initialDraft?.years ?? 20)
  const [monthlyIncome,setMonthlyIncome]=useState(initialDraft?.monthlyIncome ?? 0)
  const [existingPayments,setExistingPayments]=useState(initialDraft?.existingPayments ?? 0)
  const [employment,setEmployment]=useState<'employee'|'self'|'business'>(initialDraft?.employment ?? 'employee')
  const [childrenCount,setChildrenCount]=useState(initialDraft?.childrenCount ?? 1)
  const [youngestChildAge,setYoungestChildAge]=useState<number|null>(initialDraft?.youngestChildAge ?? 3)
  const [itAccredited,setItAccredited]=useState(initialDraft?.itAccredited ?? false)
  const [showAllBanks,setShowAllBanks]=useState(false)
  const [saved,setSaved]=useState(false)

  const program=useMemo(
    () => scenarioProgram(scenario,childrenCount,youngestChildAge,apartmentArea),
    [scenario,childrenCount,youngestChildAge,apartmentArea]
  )

  const offers=useMemo(() => buildMortgageWizardOffers({
    scenario,
    price:propertyPrice,
    downPayment,
    years,
    childrenCount,
    youngestChildAge,
    apartmentArea
  }),[scenario,propertyPrice,downPayment,years,childrenCount,youngestChildAge,apartmentArea])

  const selected=offers.find(item => item.offer.id === bankId) ?? offers[0]
  const best=offers.find(item => item.eligible && item.result) ?? offers[0]
  const downPercent=propertyPrice > 0 ? downPayment/propertyPrice*100 : 0
  const paymentLoad=selected?.result && monthlyIncome > 0 ? (selected.result.monthlyPayment+existingPayments)/monthlyIncome*100 : null
  const priceMax=Math.max(30_000_000,Math.ceil(propertyPrice*1.4/1_000_000)*1_000_000)
  const step3Offers=offers.slice(0,5)
  const otherOffers=offers.filter(item => item.offer.id !== selected?.offer.id)
  const step4Others=(showAllBanks ? otherOffers : otherOffers.slice(0,3))

  function chooseScenario(next:MortgageWizardScenario) {
    setScenario(next)
    const nextOffers=buildMortgageWizardOffers({
      scenario:next,
      price:propertyPrice,
      downPayment,
      years,
      childrenCount,
      youngestChildAge,
      apartmentArea
    })
    const currentStillExists=nextOffers.some(item => item.offer.id === bankId)
    if (!currentStillExists && nextOffers[0]) setBankId(nextOffers[0].offer.id)
  }

  function goToFinal() {
    if (!selected?.eligible && best?.eligible) setBankId(best.offer.id)
    setStep(4)
  }

  function saveCalculation() {
    if (!selected?.result) return
    try {
      saveMortgageCalculation({
        id:globalThis.crypto?.randomUUID?.() ?? `mortgage-${Date.now()}`,
        createdAt:new Date().toISOString(),
        apartmentPrice:propertyPrice,
        downPayment,
        years,
        scenario,
        bankId:selected.offer.id,
        bank:selected.offer.bank,
        rate:selected.rate,
        monthlyPayment:selected.result.monthlyPayment,
        totalPayment:selected.result.totalPayment,
        overpayment:selected.result.overpayment
      })
      setSaved(true)
    } catch {
      setSaved(false)
    }
  }

  const familyNeedsAttention=scenario === 'family' && !program.available
  const itNeedsAttention=scenario === 'it' && !itAccredited

  useEffect(() => {
    const timer=window.setTimeout(() => {
      saveMortgageWizardDraft({
        sourcePrice:initialPrice,
        step,
        scenario,
        bankId,
        propertyPrice,
        downPayment,
        years,
        monthlyIncome,
        existingPayments,
        employment,
        childrenCount,
        youngestChildAge,
        itAccredited,
        updatedAt:new Date().toISOString()
      })
    },180)
    return () => window.clearTimeout(timer)
  },[initialPrice,step,scenario,bankId,propertyPrice,downPayment,years,monthlyIncome,existingPayments,employment,childrenCount,youngestChildAge,itAccredited])

  function resetWizard() {
    clearMortgageWizardDraft()
    setStep(1)
    setScenario('secondary')
    setBankId('sber')
    setPropertyPrice(initialPrice)
    setDownPayment(initialDown)
    setYears(20)
    setMonthlyIncome(0)
    setExistingPayments(0)
    setEmployment('employee')
    setChildrenCount(1)
    setYoungestChildAge(3)
    setItAccredited(false)
    setShowAllBanks(false)
    setSaved(false)
  }

  return <section className="mortgage-wizard" aria-labelledby="mortgage-title">
    <header className="mortgage-wizard-header">
      <div>
        <span className="mortgage-wizard-kicker">GEODOM · ИПОТЕКА · КРАСНОЯРСК</span>
        <h3 id="mortgage-title">Ипотечный калькулятор</h3>
        <p>Пройдите 4 шага: программа и банк → параметры заёмщика → расчёт → итоговое предложение.</p>
      </div>
      <div className="mortgage-wizard-head-actions"><span className="mortgage-wizard-date">Данные банков: {new Date(KRASNOYARSK_MORTGAGE_SNAPSHOT_DATE).toLocaleDateString('ru-RU')}</span><button type="button" onClick={resetWizard}>Начать заново</button></div>
    </header>

    <div className="mortgage-wizard-progress" aria-label={`Шаг ${step} из 4`}>
      <div className="mortgage-wizard-bars">{[1,2,3,4].map(value => <span key={value} className={value <= step ? 'active' : ''}/>)}</div>
      <b>Шаг {step} из 4</b>
    </div>

    {step === 1 && <div className="mortgage-wizard-step">
      <div className="mortgage-step-heading">
        <span>01 / БАНК И ПРОГРАММА</span>
        <h4>Выберите банк</h4>
        <p>Сравните условия ведущих банков и выберите предложение, с которого хотите начать расчёт.</p>
      </div>

      <div className="mortgage-scenario-tabs" role="tablist" aria-label="Тип ипотечной программы">
        {SCENARIOS.map(item => <button type="button" role="tab" aria-selected={scenario === item.id} className={scenario === item.id ? 'active' : ''} key={item.id} onClick={() => chooseScenario(item.id)}>
          <span>{scenarioIcon(item.id)}</span>
          <div><b>{item.title}</b><small>{item.subtitle}</small></div>
        </button>)}
      </div>

      <div className="mortgage-step-note">
        <ShieldCheck size={16}/>
        <span>{scenario === 'newbuild'
          ? 'Для новостройки отдельного банковского feed пока нет: на карточках показан текущий банковский ориентир, а финальные условия нужно подтвердить у банка.'
          : scenario === 'family' || scenario === 'it'
            ? 'Ставка на карточках — параметр госпрограммы. Участие конкретного банка и финальные условия нужно подтвердить отдельно.'
            : 'Для вторичного жилья используем текущий frontend snapshot публичных предложений банков.'}</span>
      </div>

      <div className="mortgage-bank-choice-grid">
        {offers.map(item => <button type="button" key={item.offer.id} className={`mortgage-bank-choice ${bankId === item.offer.id ? 'active' : ''}`} onClick={() => setBankId(item.offer.id)}>
          <BankMark offer={item.offer}/>
          <span className="mortgage-bank-choice-copy"><b>{item.offer.bank}</b><small>{scenario === 'family' ? 'Семейная ипотека' : scenario === 'it' ? 'IT-ипотека' : item.offer.program}</small></span>
          <span className="mortgage-bank-choice-rate"><b>{item.rate === null ? 'Уточнить' : `от ${item.rate}%`}</b><small>{item.eligible ? 'можно рассчитать' : item.reasons[0] || 'нужно уточнить'}</small></span>
          <span className="mortgage-bank-radio">{bankId === item.offer.id && <Check size={13}/>}</span>
        </button>)}
      </div>

      <div className="mortgage-wizard-actions end">
        <button type="button" className="mortgage-wizard-primary" onClick={() => setStep(2)}>Продолжить <ArrowRight size={17}/></button>
      </div>
    </div>}

    {step === 2 && <div className="mortgage-wizard-step">
      <div className="mortgage-step-heading">
        <span>02 / ПАРАМЕТРЫ ЗАЁМЩИКА</span>
        <h4>Проверьте свой сценарий</h4>
        <p>Эти данные не отправляются в банк. Они помогают показать нагрузку и проверить базовые условия выбранной программы.</p>
      </div>

      <div className="mortgage-borrower-grid">
        <label><span>Доход семьи в месяц</span><div><input type="number" min="0" step="5000" value={monthlyIncome || ''} placeholder="Например, 180000" onChange={event => setMonthlyIncome(Math.max(0,Number(event.target.value)))}/><em>₽</em></div><small>Необязательно, но пригодится для оценки нагрузки.</small></label>
        <label><span>Другие платежи по кредитам</span><div><input type="number" min="0" step="1000" value={existingPayments || ''} placeholder="0" onChange={event => setExistingPayments(Math.max(0,Number(event.target.value)))}/><em>₽/мес</em></div><small>Кредитки, автокредиты и другие регулярные платежи.</small></label>
        <label><span>Формат занятости</span><div className="mortgage-borrower-select"><select value={employment} onChange={event => setEmployment(event.target.value as typeof employment)}><option value="employee">Наёмный сотрудник</option><option value="self">Самозанятый</option><option value="business">ИП / владелец бизнеса</option></select><ChevronDown size={15}/></div><small>Пока используется как часть профиля, а не как банковское решение.</small></label>
        <div className="mortgage-borrower-bank"><BankMark offer={selected.offer} size="large"/><div><span>Выбранный банк</span><b>{selected.offer.bank}</b><small>{selected.rate === null ? 'ставка уточняется' : `${selected.rate}% в текущем сценарии`}</small></div></div>
      </div>

      {scenario === 'family' && <div className="mortgage-program-check">
        <div><Baby size={18}/><span><b>Семейная ипотека</b><small>Уточним параметры семьи для проверки льготного сценария.</small></span></div>
        <label><span>Количество детей</span><select value={childrenCount} onChange={event => setChildrenCount(Number(event.target.value))}>{[1,2,3,4,5,6].map(value => <option value={value} key={value}>{value}</option>)}</select></label>
        <label><span>Возраст младшего</span><select value={youngestChildAge ?? ''} onChange={event => setYoungestChildAge(event.target.value === '' ? null : Number(event.target.value))}><option value="">Не указан</option>{Array.from({length:18},(_,index) => <option value={index} key={index}>{index} {index === 1 ? 'год' : index > 1 && index < 5 ? 'года' : 'лет'}</option>)}</select></label>
      </div>}

      {scenario === 'it' && <label className="mortgage-it-check"><input type="checkbox" checked={itAccredited} onChange={event => setItAccredited(event.target.checked)}/><BriefcaseBusiness size={18}/><span><b>Работаю в аккредитованной IT-компании</b><small>Это frontend-проверка сценария. Реальную аккредитацию и требования подтверждает банк.</small></span></label>}

      {(familyNeedsAttention || itNeedsAttention) && <div className="mortgage-step-warning">{familyNeedsAttention ? program.warning || 'Проверьте параметры семейной программы.' : 'Для IT-ипотеки нужно подтвердить работу в аккредитованной IT-компании.'}</div>}

      <div className="mortgage-wizard-actions">
        <button type="button" className="mortgage-wizard-secondary" onClick={() => setStep(1)}><ArrowLeft size={16}/> Назад</button>
        <button type="button" className="mortgage-wizard-primary" onClick={() => setStep(3)}>К параметрам ипотеки <ArrowRight size={17}/></button>
      </div>
    </div>}

    {step === 3 && <div className="mortgage-wizard-step">
      <div className="mortgage-step-heading">
        <span>03 / ПАРАМЕТРЫ И ПРЕДЛОЖЕНИЯ</span>
        <h4>Параметры ипотеки</h4>
        <p>Изменяйте сумму, взнос и срок — предложения пересортируются по расчётному ежемесячному платежу.</p>
      </div>

      <div className="mortgage-parameter-grid">
        <label>
          <span>Стоимость жилья <b>{formatPrice(Math.round(propertyPrice))}</b></span>
          <input type="range" min="300000" max={priceMax} step="50000" value={propertyPrice} onChange={event => { const next=Number(event.target.value);setPropertyPrice(next);setDownPayment(current => Math.min(current,next)) }}/>
          <div><small>300 000 ₽</small><input type="number" min="300000" step="50000" value={propertyPrice} onChange={event => { const next=Math.max(300_000,Number(event.target.value) || 300_000);setPropertyPrice(next);setDownPayment(current => Math.min(current,next)) }}/><small>{formatPrice(priceMax)}</small></div>
        </label>
        <label>
          <span>Первоначальный взнос <b>{formatPrice(Math.round(downPayment))}</b></span>
          <input type="range" min="0" max={propertyPrice} step="10000" value={downPayment} onChange={event => setDownPayment(Number(event.target.value))}/>
          <div><small>0 ₽</small><input type="number" min="0" max={propertyPrice} step="10000" value={downPayment} onChange={event => setDownPayment(clamp(Number(event.target.value),0,propertyPrice))}/><small>{downPercent.toFixed(1)}%</small></div>
        </label>
        <label>
          <span>Срок <b>{years} лет</b></span>
          <input type="range" min="1" max="30" step="1" value={years} onChange={event => setYears(Number(event.target.value))}/>
          <div><small>1 год</small><select value={years} onChange={event => setYears(Number(event.target.value))}>{[5,10,15,20,25,30].map(value => <option key={value} value={value}>{value} лет</option>)}</select><small>30 лет</small></div>
        </label>
        <label className="mortgage-program-select-card">
          <span>Программа</span>
          <div><span>{scenarioIcon(scenario)}</span><select value={scenario} onChange={event => chooseScenario(event.target.value as MortgageWizardScenario)}>{SCENARIOS.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select><ChevronDown size={15}/></div>
          <small>Можно изменить программу на этом шаге.</small>
        </label>
      </div>

      <div className="mortgage-offers-head">
        <div><span>ЛУЧШИЕ ПРЕДЛОЖЕНИЯ</span><h5>{step3Offers.filter(item => item.eligible).length} предложений, отсортированных по расчётной выгоде</h5></div>
        <small>{scenario === 'family' || scenario === 'it' ? 'Для льготных программ ставка общая; участие банка нужно подтвердить.' : scenario === 'newbuild' ? 'Ставки новостройки пока ориентировочные.' : 'На основе текущего банковского snapshot.'}</small>
      </div>

      <div className="mortgage-offer-list">
        {step3Offers.map((item,index) => <button type="button" key={item.offer.id} className={`mortgage-offer-row ${bankId === item.offer.id ? 'active' : ''} ${!item.eligible ? 'disabled' : ''}`} onClick={() => setBankId(item.offer.id)}>
          <BankMark offer={item.offer}/>
          <span className="mortgage-offer-bank"><b>{item.offer.bank}</b><small>{scenarioLabel(scenario)}</small></span>
          <span><small>Ставка</small><b>{item.rate === null ? '—' : `${item.rate}%`}</b></span>
          <span><small>Платёж в месяц</small><b>{item.result ? formatPrice(Math.round(item.result.monthlyPayment)) : 'Не проходит'}</b></span>
          <span className="mortgage-offer-choice">{bankId === item.offer.id ? <Check size={15}/> : index+1}</span>
        </button>)}
      </div>

      <div className="mortgage-wizard-actions">
        <button type="button" className="mortgage-wizard-secondary" onClick={() => setStep(2)}><ArrowLeft size={16}/> Назад</button>
        <button type="button" className="mortgage-wizard-primary" onClick={goToFinal}>Показать расчёт <ArrowRight size={17}/></button>
      </div>
    </div>}

    {step === 4 && <div className="mortgage-wizard-step">
      <div className="mortgage-step-heading final">
        <span>04 / РЕЗУЛЬТАТ</span>
        <h4>Ваш расчёт готов</h4>
        <p>Вы можете вернуться к параметрам, выбрать другой банк или сохранить расчёт.</p>
      </div>

      <div className="mortgage-final-featured">
        <div className="mortgage-final-badge"><Sparkles size={14}/>{selected.offer.id === best.offer.id ? 'Лучшее предложение по текущему расчёту' : 'Выбранное предложение'}</div>
        <div className="mortgage-final-bank">
          <BankMark offer={selected.offer} size="large"/>
          <div><h5>{selected.offer.bank}</h5><p>{scenarioLabel(scenario)} · {selected.offer.program}</p></div>
          <a href={selected.offer.sourceUrl} target="_blank" rel="noopener noreferrer">Источник <ArrowUpRight size={14}/></a>
        </div>

        <div className="mortgage-final-metrics">
          <div><span>Ставка</span><b>{selected.rate === null ? '—' : `${selected.rate}%`}</b></div>
          <div className="payment"><span>Платёж в месяц</span><b>{selected.result ? formatPrice(Math.round(selected.result.monthlyPayment)) : '—'}</b></div>
          <div><span>Сумма кредита</span><b>{selected.result ? formatPrice(Math.round(selected.result.principal)) : formatPrice(Math.max(0,propertyPrice-downPayment))}</b></div>
          <div><span>Первоначальный взнос</span><b>{formatPrice(Math.round(downPayment))}</b></div>
          <div><span>Срок</span><b>{years} лет</b></div>
          <div><span>Переплата</span><b>{selected.result ? formatPrice(Math.round(selected.result.overpayment)) : '—'}</b></div>
        </div>

        {paymentLoad !== null && <div className="mortgage-final-load"><UserRound size={15}/><span>Платежи после ипотеки составят примерно <b>{paymentLoad.toFixed(0)}%</b> указанного месячного дохода. Это только ориентир, а не банковская оценка платёжеспособности.</span></div>}
        {!selected.eligible && <div className="mortgage-final-warning">{selected.reasons[0] || 'Текущие параметры нужно уточнить у банка.'}</div>}
      </div>

      <div className="mortgage-other-head">
        <div><h5>Другие варианты</h5><p>Можно переключиться на другой банк без возврата к началу.</p></div>
        <button type="button" onClick={() => setShowAllBanks(value => !value)}>{showAllBanks ? 'Скрыть часть' : 'Все предложения'} <ArrowRight size={14}/></button>
      </div>

      <div className="mortgage-other-grid">
        {step4Others.map(item => <button type="button" key={item.offer.id} onClick={() => setBankId(item.offer.id)} className={!item.eligible ? 'disabled' : ''}>
          <BankMark offer={item.offer}/>
          <span><b>{item.offer.bank}</b><small>{item.rate === null ? 'Ставка уточняется' : `${item.rate}%`}</small></span>
          <strong>{item.result ? formatPrice(Math.round(item.result.monthlyPayment))+'/мес' : 'Уточнить'}</strong>
          <ArrowRight size={14}/>
        </button>)}
      </div>

      <div className="mortgage-final-actions">
        <a className="mortgage-apply-button" href={selected.offer.sourceUrl} target="_blank" rel="noopener noreferrer">Подать заявку <ArrowRight size={18}/></a>
        <button type="button" className={saved ? 'saved' : ''} onClick={saveCalculation}><Save size={17}/>{saved ? 'Расчёт сохранён' : 'Сохранить расчёт'}</button>
      </div>
      <p className="mortgage-final-footnote">Сейчас «Подать заявку» открывает источник выбранного предложения. Партнёрская отправка заявки появится после backend-интеграции.</p>

      <div className="mortgage-wizard-actions start">
        {onCompareRent && selected.result && selected.rate !== null && <button type="button" className="mortgage-wizard-primary" onClick={() => {
          if (selected.rate !== null) onCompareRent({apartmentPrice:propertyPrice,downPayment,annualRate:selected.rate,mortgageYears:years})
        }}>Сравнить с арендой <ArrowRight size={17}/></button>}
        <button type="button" className="mortgage-wizard-secondary" onClick={() => setStep(3)}><ArrowLeft size={16}/> Изменить параметры</button>
      </div>
    </div>}
  </section>
}
