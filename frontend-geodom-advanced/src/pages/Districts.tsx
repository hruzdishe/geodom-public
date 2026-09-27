import { useEffect,useMemo,useState } from 'react'
import { ArrowLeft, ArrowRight, Building2, Calculator, Camera, ChevronDown, Home, Landmark, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { price } from '../lib/catalog'
import type { DistrictStats } from '../lib/districtStats'
import { calculateMortgage } from '../components/MortgageCalculator'
import { PageLoading, EmptyState } from '../components/Ui'
import { useGeoDomStore } from '../store/useGeoDomStore'

type SortMode='score'|'price'|'price_m2'|'count'

function formatNumber(value:number|null,suffix='') {
  return value === null ? '—' : `${new Intl.NumberFormat('ru-RU',{ maximumFractionDigits:1 }).format(value)}${suffix}`
}

export function Districts() {
  const [stats,setStats]=useState<DistrictStats[]>([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [sort,setSort]=useState<SortMode>('score')
  const [annualRate,setAnnualRate]=useState<number|null>(null)
  const [years,setYears]=useState(20)
  const preferences=useGeoDomStore(state => state.preferences)

  useEffect(() => {
    api.districtStats().then(setStats).catch(error => setError(error instanceof Error ? error.message : 'Не удалось загрузить статистику районов')).finally(() => setLoading(false))
  },[])
  const sorted=useMemo(() => [...stats].sort((a,b) => {
    if (sort === 'count') return b.count-a.count
    if (sort === 'price') return (a.medianPrice ?? Infinity)-(b.medianPrice ?? Infinity)
    if (sort === 'price_m2') return (a.medianPriceM2 ?? Infinity)-(b.medianPriceM2 ?? Infinity)
    return (b.averageScore ?? -1)-(a.averageScore ?? -1)
  }),[stats,sort])

  const withInventory=stats.filter(item => item.count > 0)
  const total=withInventory.reduce((sum,item) => sum+item.count,0)
  const medianCityPrice=withInventory.length
    ? [...withInventory].map(item => item.medianPrice).filter((value):value is number => value !== null).sort((a,b) => a-b)[Math.floor(withInventory.length/2)] ?? null
    : null

  return <div className="district-explorer-page">
    <div className="shell">
      <div className="district-explorer-toolbar">
        <Link to="/" className="back-link"><ArrowLeft size={17}/> На главную</Link>
        <Link to="/#main-map" className="button light">Открыть карту <ArrowRight size={15}/></Link>
      </div>

      <header className="district-explorer-head">
        <div>
          <span>GEODOM / 7 РАЙОНОВ КРАСНОЯРСКА</span>
          <h1>Сравните районы по реальным объектам каталога</h1>
          <p>Здесь нет отдельной «оценки района из воздуха»: показатели считаются из текущих квартир, их цены, площади, фотографий и доступного score.</p>
        </div>
        <div className="district-explorer-summary">
          <div><small>Квартир в выборке</small><b>{total}</b></div>
          <div><small>Районов с данными</small><b>{withInventory.length} / 7</b></div>
          <div><small>Медиана района</small><b>{medianCityPrice ? price(Math.round(medianCityPrice)) : '—'}</b></div>
        </div>
      </header>

      <section className="district-affordability">
        <div className="district-affordability-copy">
          <span><Calculator size={16}/> ФИНАНСОВЫЙ СЦЕНАРИЙ</span>
          <h2>Посмотрите ориентировочный платёж по медианной квартире каждого района</h2>
          <p>Первоначальный взнос берём из ваших параметров GeoDom. Ставку не угадываем — укажите условия конкретного банка или программы.</p>
        </div>
        <div className="district-affordability-controls">
          <label><span>Ваш взнос</span><b>{price(preferences.down_payment)}</b></label>
          <label><span>Ставка, %</span><input type="number" min="0" max="100" step=".1" value={annualRate ?? ''} placeholder="Например, 18.5" onChange={event => setAnnualRate(event.target.value === '' ? null : Math.max(0,Number(event.target.value)))}/></label>
          <label><span>Срок</span><select value={years} onChange={event => setYears(Number(event.target.value))}>{[5,10,15,20,25,30].map(value => <option value={value} key={value}>{value} лет</option>)}</select></label>
        </div>
      </section>

      <div className="district-explorer-controls">
        <div><Building2 size={17}/><b>Районы</b><span>всегда показываем все 7, даже если по части пока нет квартир</span></div>
        <label>Сортировать
          <div className="select-wrap">
            <select value={sort} onChange={event => setSort(event.target.value as SortMode)}>
              <option value="score">По score</option>
              <option value="price">По медианной цене</option>
              <option value="price_m2">По цене за м²</option>
              <option value="count">По числу квартир</option>
            </select>
            <ChevronDown size={15}/>
          </div>
        </label>
      </div>

      {loading
        ? <PageLoading/>
        : error
          ? <EmptyState title="Не удалось загрузить районы" message={error}/>
          : <div className="district-explorer-grid">{sorted.map(district => <DistrictCard
              key={district.id}
              district={district}
              budget={preferences.budget_max}
              downPayment={preferences.down_payment}
              annualRate={annualRate}
              years={years}
            />)}</div>}
    </div>
  </div>
}

function DistrictCard({
  district,
  budget,
  downPayment,
  annualRate,
  years
}:{
  district:DistrictStats
  budget:number
  downPayment:number
  annualRate:number|null
  years:number
}) {
  const mortgage=district.medianPrice !== null && annualRate !== null
    ? calculateMortgage(district.medianPrice,Math.min(downPayment,district.medianPrice),annualRate,years)
    : null
  const withinBudget=district.medianPrice !== null && budget > 0 ? district.medianPrice <= budget : null
  const query=`/?district=${encodeURIComponent(district.name)}#catalog`

  return <article className={`district-explorer-card ${district.count ? '' : 'empty'}`}>
    <div className="district-explorer-card-head">
      <div><span>{district.count ? `${district.count} квартир` : 'Нет квартир в текущей выборке'}</span><h2>{district.name}</h2></div>
      <div className="district-score"><Sparkles size={14}/><b>{district.averageScore?.toFixed(1) ?? '—'}</b><small>/10</small></div>
    </div>

    <div className="district-metrics">
      <div><span>Медианная цена</span><b>{district.medianPrice ? price(Math.round(district.medianPrice)) : '—'}</b></div>
      <div><span>Медиана за м²</span><b>{district.medianPriceM2 ? `${price(Math.round(district.medianPriceM2))}/м²` : '—'}</b></div>
      <div><span>Медианная площадь</span><b>{formatNumber(district.medianArea,' м²')}</b></div>
      <div><span>С фотографиями</span><b>{district.photoCoverage === null ? '—' : `${Math.round(district.photoCoverage*100)}%`}</b></div>
    </div>

    <div className="district-range">
      <Home size={14}/><span>Диапазон цен</span><b>{district.minPrice !== null && district.maxPrice !== null ? `${price(Math.round(district.minPrice))} — ${price(Math.round(district.maxPrice))}` : '—'}</b>
    </div>

    <div className="district-budget-row">
      <span>Ваш бюджет</span>
      <b className={withinBudget === true ? 'fit' : withinBudget === false ? 'over' : ''}>{withinBudget === null ? '—' : withinBudget ? 'Медиана входит' : 'Медиана выше бюджета'}</b>
    </div>

    <div className="district-mortgage-row">
      <Landmark size={14}/>
      <span>Платёж по медиане</span>
      <b>{mortgage ? `${price(Math.round(mortgage.monthlyPayment))}/мес` : district.medianPrice ? 'Введите ставку' : '—'}</b>
    </div>

    <div className="district-photo-row"><Camera size={13}/><span>{district.count ? `Фото есть у ${Math.round((district.photoCoverage ?? 0)*100)}% объявлений` : 'Нет данных для оценки покрытия фото'}</span></div>

    <Link className={`district-open-link ${district.count ? '' : 'disabled'}`} to={district.count ? query : '/districts'} aria-disabled={!district.count}>
      Смотреть квартиры района <ArrowRight size={15}/>
    </Link>
  </article>
}
