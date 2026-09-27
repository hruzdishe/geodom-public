import { useState } from 'react'
import { ArrowRightLeft, Home, Landmark, TrendingUp } from 'lucide-react'
import { price } from '../lib/catalog'
import { calculateMortgage } from './MortgageCalculator'
import { KRASNOYARSK_MORTGAGE_BANKS,mortgageOfferEligibility } from '../lib/mortgageBanks'

export type RentVsBuyInput = {
  apartmentPrice:number
  downPayment:number
  annualRate:number
  years:number
  mortgageYears:number
  monthlyRent:number
  rentGrowthPercent:number
  homeGrowthPercent:number
  maintenancePercent:number
  investmentReturnPercent:number
  purchaseCostsPercent:number
  saleCostsPercent:number
}

export type RentVsBuyResult = {
  buyerNetWorth:number
  renterNetWorth:number
  difference:number
  futureHomeValue:number
  remainingMortgage:number
  renterPortfolio:number
  buyerPortfolio:number
  monthlyMortgage:number
  totalRentPaid:number
  purchaseCosts:number
  saleCosts:number
  totalMortgagePaid:number
  totalMaintenancePaid:number
}

// Both scenarios start with identical cash and have the same monthly budget.
// The cheaper scenario invests the monthly saving at the end of each month.
export function validateRentVsBuy(input:RentVsBuyInput):string | null {
  if (Object.values(input).some(value => !Number.isFinite(value))) return 'Заполните все поля числами.'
  if (input.apartmentPrice <= 0) return 'Стоимость квартиры должна быть больше нуля.'
  if (input.downPayment < 0 || input.downPayment > input.apartmentPrice) return 'Взнос должен быть от 0 до стоимости квартиры.'
  if (input.monthlyRent < 0) return 'Аренда не может быть отрицательной.'
  if (input.years < 1/12 || input.years > 50 || input.mortgageYears < 1 || input.mortgageYears > 50) return 'Срок сравнения: от 1 месяца до 50 лет. Срок ипотеки: от 1 до 50 лет.'
  if (input.annualRate < 0 || input.annualRate > 100) return 'Ставка ипотеки должна быть от 0 до 100%.'
  if ([input.rentGrowthPercent,input.homeGrowthPercent,input.investmentReturnPercent].some(value => value <= -100 || value > 100)) return 'Рост цен и доходность должны быть больше −100% и не больше 100% в год.'
  if ([input.maintenancePercent,input.purchaseCostsPercent,input.saleCostsPercent].some(value => value < 0 || value > 100)) return 'Расходы должны быть от 0 до 100%.'
  return null
}

function monthlyRate(annualPercent:number) {
  return Math.expm1(Math.log1p(annualPercent/100)/12)
}

export function calculateRentVsBuy(input:RentVsBuyInput):RentVsBuyResult {
  const error=validateRentVsBuy(input)
  if (error) throw new RangeError(error)
  const horizonMonths=Math.round(input.years*12)
  const mortgage=calculateMortgage(input.apartmentPrice,input.downPayment,input.annualRate,input.mortgageYears)
  const mortgageMonths=Math.round(input.mortgageYears*12)
  const loanRate=input.annualRate/100/12
  const homeGrowth=monthlyRate(input.homeGrowthPercent)
  const rentGrowth=monthlyRate(input.rentGrowthPercent)
  const investmentGrowth=monthlyRate(input.investmentReturnPercent)
  const purchaseCosts=input.apartmentPrice*input.purchaseCostsPercent/100
  let homeValue=input.apartmentPrice
  let rent=input.monthlyRent
  let remainingMortgage=mortgage.principal
  let renterPortfolio=input.downPayment+purchaseCosts
  let buyerPortfolio=0
  let totalRentPaid=0
  let totalMortgagePaid=0
  let totalMaintenancePaid=0

  for (let month=1;month<=horizonMonths;month++) {
    renterPortfolio*=1+investmentGrowth
    buyerPortfolio*=1+investmentGrowth
    const mortgagePayment=month <= mortgageMonths ? Math.min(mortgage.monthlyPayment,remainingMortgage*(1+loanRate)) : 0
    remainingMortgage=month >= mortgageMonths ? 0 : Math.max(0,remainingMortgage*(1+loanRate)-mortgagePayment)
    const maintenance=homeValue*input.maintenancePercent/100/12
    totalRentPaid+=rent
    totalMortgagePaid+=mortgagePayment
    totalMaintenancePaid+=maintenance

    const saving=mortgagePayment+maintenance-rent
    if (saving > 0) renterPortfolio+=saving
    else buyerPortfolio-=saving

    // The entered rent is the first month's rent; growth applies to the next month.
    homeValue*=1+homeGrowth
    rent*=1+rentGrowth
  }

  const saleCosts=homeValue*input.saleCostsPercent/100
  // Debt still has to be repaid even when sale proceeds cannot cover it.
  const buyerNetWorth=homeValue-remainingMortgage-saleCosts+buyerPortfolio
  return {
    buyerNetWorth,
    renterNetWorth:renterPortfolio,
    difference:buyerNetWorth-renterPortfolio,
    futureHomeValue:homeValue,
    remainingMortgage,
    renterPortfolio,
    buyerPortfolio,
    monthlyMortgage:mortgage.monthlyPayment,
    totalRentPaid,
    purchaseCosts,
    saleCosts,
    totalMortgagePaid,
    totalMaintenancePaid
  }
}

export function RentVsBuyCalculator({
  apartmentPrice,
  defaultDownPayment=Math.round(apartmentPrice*.2),
  defaultAnnualRate=15,
  defaultMortgageYears=20
}:{
  apartmentPrice:number
  defaultDownPayment?:number
  defaultAnnualRate?:number
  defaultMortgageYears?:number
}) {
  const [bankId,setBankId]=useState('custom')
  const [annualRate,setAnnualRate]=useState(defaultAnnualRate)
  const [downPayment,setDownPayment]=useState(Math.min(apartmentPrice,defaultDownPayment))
  const [years,setYears]=useState(10)
  const [mortgageYears,setMortgageYears]=useState(defaultMortgageYears)
  const [monthlyRent,setMonthlyRent]=useState(40_000)
  const [rentGrowth,setRentGrowth]=useState(5)
  const [homeGrowth,setHomeGrowth]=useState(4)
  const [maintenance,setMaintenance]=useState(1)
  const [investmentReturn,setInvestmentReturn]=useState(8)
  const [purchaseCosts,setPurchaseCosts]=useState(1)
  const [saleCosts,setSaleCosts]=useState(2)
  const [advanced,setAdvanced]=useState(false)

  const bank=KRASNOYARSK_MORTGAGE_BANKS.find(item => item.id === bankId)
  const eligibility=bank ? mortgageOfferEligibility(bank,apartmentPrice,downPayment,mortgageYears) : null
  const input:RentVsBuyInput={
    apartmentPrice,downPayment,annualRate,years,mortgageYears,monthlyRent,
    rentGrowthPercent:rentGrowth,homeGrowthPercent:homeGrowth,maintenancePercent:maintenance,
    investmentReturnPercent:investmentReturn,purchaseCostsPercent:purchaseCosts,saleCostsPercent:saleCosts
  }
  const error=validateRentVsBuy(input)
  const result=error ? null : calculateRentVsBuy(input)
  const tied=result !== null && Math.abs(result.difference) < 1

  return <section className="rent-buy-calculator" id="rent-buy-comparison">
    <div className="rent-buy-head">
      <span><ArrowRightLeft size={17}/></span>
      <div><small>КУПИТЬ ИЛИ СНИМАТЬ</small><h3>Что выгоднее на выбранный срок</h3></div>
    </div>

    <p className="rent-buy-summary">Квартира: {price(apartmentPrice)}. Сравните капитал, который останется при покупке и при аренде.</p>
    <div className="rent-buy-core-fields">
      <label><span>Аренда сейчас, ₽/мес</span><input type="number" min="0" step="1000" value={Number.isFinite(monthlyRent) ? monthlyRent : ''} onChange={event => setMonthlyRent(event.target.valueAsNumber)}/></label>
      <label><span>Первоначальный взнос, ₽</span><input type="number" min="0" max={apartmentPrice} step="10000" value={Number.isFinite(downPayment) ? downPayment : ''} onChange={event => setDownPayment(event.target.valueAsNumber)}/></label>
      <label><span>Пример ставки банка</span><select value={bankId} onChange={event => {
        const selected=KRASNOYARSK_MORTGAGE_BANKS.find(item => item.id === event.target.value)
        setBankId(event.target.value)
        if (selected?.rateFrom != null) setAnnualRate(selected.rateFrom)
      }}><option value="custom">Свои условия</option>{KRASNOYARSK_MORTGAGE_BANKS.filter(item => item.rateFrom !== null).map(item => <option value={item.id} key={item.id}>{item.bank} · от {item.rateFrom}%</option>)}</select></label>
      <label><span>Ваша ставка ипотеки, % / год</span><input type="number" min="0" max="100" step=".1" value={Number.isFinite(annualRate) ? annualRate : ''} onChange={event => {setAnnualRate(event.target.valueAsNumber);setBankId('custom')}}/></label>
      <label><span>Срок сравнения, лет</span><input type="number" min="1" max="50" step="1" value={Number.isFinite(years) ? years : ''} onChange={event => setYears(event.target.valueAsNumber)}/></label>
      <label><span>Срок ипотеки, лет</span><input type="number" min="1" max="50" step="1" value={Number.isFinite(mortgageYears) ? mortgageYears : ''} onChange={event => setMortgageYears(event.target.valueAsNumber)}/></label>
    </div>
    {bank && <p className="rent-buy-summary">Пример из сохранённых условий на {bank.updatedAt}, не персональное предложение. Укажите фактическую ставку банка.</p>}

    <button type="button" className="rent-buy-advanced-toggle" aria-expanded={advanced} onClick={() => setAdvanced(value => !value)}>{advanced ? 'Скрыть допущения' : 'Настроить допущения'}</button>
    {advanced && <div className="rent-buy-assumptions">
      <label><span>Рост аренды / год</span><input type="number" min="-99.9" max="100" step=".5" value={Number.isFinite(rentGrowth) ? rentGrowth : ''} onChange={event => setRentGrowth(event.target.valueAsNumber)}/><small>%</small></label>
      <label><span>Рост цены жилья / год</span><input type="number" min="-99.9" max="100" step=".5" value={Number.isFinite(homeGrowth) ? homeGrowth : ''} onChange={event => setHomeGrowth(event.target.valueAsNumber)}/><small>%</small></label>
      <label><span>Содержание жилья / год</span><input type="number" min="0" max="100" step=".25" value={Number.isFinite(maintenance) ? maintenance : ''} onChange={event => setMaintenance(event.target.valueAsNumber)}/><small>% стоимости: ремонт, страховка, налог</small></label>
      <label><span>Доходность свободных денег</span><input type="number" min="-99.9" max="100" step=".5" value={Number.isFinite(investmentReturn) ? investmentReturn : ''} onChange={event => setInvestmentReturn(event.target.valueAsNumber)}/><small>% / год после налогов и комиссий; 0% — без инвестирования</small></label>
      <label><span>Расходы при покупке</span><input type="number" min="0" max="100" step=".5" value={Number.isFinite(purchaseCosts) ? purchaseCosts : ''} onChange={event => setPurchaseCosts(event.target.valueAsNumber)}/><small>% цены квартиры сверх взноса</small></label>
      <label><span>Расходы при продаже</span><input type="number" min="0" max="100" step=".5" value={Number.isFinite(saleCosts) ? saleCosts : ''} onChange={event => setSaleCosts(event.target.valueAsNumber)}/><small>% будущей цены квартиры</small></label>
    </div>}

    {error && <div className="rent-buy-warning" role="alert">{error}</div>}
    {!error && bank && eligibility && !eligibility.eligible && downPayment < apartmentPrice && <div className="rent-buy-warning">{bank.bank}: {eligibility.reasons.join(' · ')}. Одобрение кредита проверяется отдельно.</div>}

    {result && <div className="rent-buy-result" aria-live="polite">
      <div className={`rent-buy-difference ${result.difference >= 0 ? 'buy-ahead' : 'rent-ahead'}`}>
        <span>При этих условиях · срок {years} г.</span>
        <b>{tied ? 'Варианты равноценны по капиталу' : `${result.difference > 0 ? 'Выгоднее купить' : 'Выгоднее снимать'}: на ${price(Math.round(Math.abs(result.difference)))}`}</b>
      </div>
      <div className="rent-buy-column buy">
        <span><Home size={14}/> ПОКУПКА</span>
        <strong>{price(Math.round(result.buyerNetWorth))}</strong>
        <small>капитал после продажи и погашения долга</small>
        <p>Жильё: {price(Math.round(result.futureHomeValue))}<br/>Остаток кредита: {price(Math.round(result.remainingMortgage))}<br/>Расходы продажи: {price(Math.round(result.saleCosts))}<br/>Накопления: {price(Math.round(result.buyerPortfolio))}<br/>Ипотека: {price(Math.round(result.monthlyMortgage))}/мес<br/>Платежи по ипотеке за период: {price(Math.round(result.totalMortgagePaid))}<br/>Содержание за период: {price(Math.round(result.totalMaintenancePaid))}</p>
      </div>
      <div className="rent-buy-column rent">
        <span><TrendingUp size={14}/> АРЕНДА + КАПИТАЛ</span>
        <strong>{price(Math.round(result.renterNetWorth))}</strong>
        <small>модельный инвестиционный капитал</small>
        <p>Аренда за период: {price(Math.round(result.totalRentPaid))}<br/>Начальный капитал: {price(Math.round(downPayment+result.purchaseCosts))}</p>
      </div>
    </div>}

    <p className="rent-buy-note"><Landmark size={14}/><span>У обоих вариантов одинаковые стартовые деньги и ежемесячный бюджет. При аренде сохраняются взнос и расходы покупки; каждый месяц более дешёвый вариант откладывает разницу. В конце срока квартиру условно продаём и вычитаем долг и расходы продажи. Ставка ипотеки фиксированная; рост аренды, цены жилья и доходность начисляются помесячно. Доходность и рост цен — ваши допущения, не прогноз. Общие коммунальные расходы, вычеты и досрочные платежи не учтены. Расходы собственника задаются в допущениях. Суммы указаны в будущих рублях без поправки на инфляцию.</span></p>
  </section>
}
