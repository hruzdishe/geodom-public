import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, ArrowUpRight, BellRing, Building2, ChevronDown, CircleHelp, MapPin, Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApartmentCard, EmptyState, PageLoading } from '../components/Ui'
import { MapPanel } from '../components/MapPanel'
import { PreferencePanel } from '../components/PreferencePanel'
import { RecommendationResults } from '../components/RecommendationResults'
import { Reveal } from '../components/MotionPrimitives'
import { api, isDemo } from '../lib/api'
import { filterApartments } from '../lib/catalog'
import { validatePreferences } from '../lib/preferences'
import { loadLastRecommendation } from '../lib/recommendations'
import type { GeoObject } from '../lib/dataSanitizers'
import type { Apartment, CatalogFilters, CatalogSort, RecommendationRequest, RecommendationResponse } from '../types'
import { useGeoDomStore } from '../store/useGeoDomStore'
import { KRASNOYARSK_DISTRICTS } from '../lib/krasnoyarsk'
import { loadPromotedIds } from '../lib/pro'
import { createSavedSearch } from '../lib/savedSearches'

const CitySignal = lazy(() => import('../components/CitySignal'))
const CATALOG_PAGE_SIZE = 24

export function Catalog() {
  const [items,setItems] = useState<Apartment[]>([])
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [geoObjects,setGeoObjects] = useState<GeoObject[]>([])
  const [geoError,setGeoError] = useState('')
  const [params,setParams] = useSearchParams()
  const preferences = useGeoDomStore(state => state.preferences)
  const filters = useGeoDomStore(state => state.filters)
  const user = useGeoDomStore(state => state.user)
  const filtersOpen = useGeoDomStore(state => state.filtersOpen)
  const workPicking = useGeoDomStore(state => state.workPicking)
  const setPreferences = useGeoDomStore(state => state.setPreferences)
  const setFilter = useGeoDomStore(state => state.setFilter)
  const resetFilters = useGeoDomStore(state => state.resetFilters)
  const resetPreferencesState = useGeoDomStore(state => state.resetPreferences)
  const setFiltersOpen = useGeoDomStore(state => state.setFiltersOpen)
  const setWorkPicking = useGeoDomStore(state => state.setWorkPicking)
  const setWorkLocation = useGeoDomStore(state => state.setWorkLocation)
  const [response,setResponse] = useState<RecommendationResponse|null>(loadLastRecommendation)
  const [recommendationLoading,setRecommendationLoading] = useState(() => !loadLastRecommendation())
  const [recommendationError,setRecommendationError] = useState('')
  const [validationError,setValidationError] = useState('')
  const [savedSearchMessage,setSavedSearchMessage] = useState('')
  const [shownCount,setShownCount] = useState(CATALOG_PAGE_SIZE)
  const requestSequence=useRef(0)
  const recommendationInput=useMemo(() => ({...preferences,catalog_filters:filters}),[preferences,filters])
  const requestSignature=JSON.stringify(recommendationInput)

  useEffect(() => {
    const district = params.get('district')
    const query = params.get('q')
    if (district !== null) setFilter('district',district)
    if (query !== null) setFilter('query',query)
  },[])

  useEffect(() => {
    api.list().then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
    api.geoObjects().then(setGeoObjects).catch(e => setGeoError(e instanceof Error ? e.message : 'Не удалось загрузить инфраструктуру'))
  },[])

  useEffect(() => {
    setRecommendationLoading(true)
    const timer=window.setTimeout(() => {
      if (validatePreferences(preferences)) { setRecommendationLoading(false); return }
      void recommend(preferences)
    },350)
    return () => { window.clearTimeout(timer); requestSequence.current+=1 }
  },[requestSignature])

  const districts = useMemo(() => [...new Set(items.map(x => x.district.name))].filter(x => x !== 'Уточняется').sort(),[items])
  const buildingTypes = useMemo(() => [...new Set(items.map(item => item.building_type).filter((value):value is string => !!value))].sort(),[items])
  const visible = useMemo(() => filterApartments(items,filters,preferences),[items,filters,preferences.work_location,preferences.max_commute_minutes])
  const shownApartments = useMemo(() => visible.slice(0,shownCount),[visible,shownCount])
  const promotedIds = useMemo(() => new Set(isDemo ? loadPromotedIds() : []),[])
  const promotedApartments = useMemo(() => visible.filter(item => promotedIds.has(item.id)).slice(0,3),[visible,promotedIds])
  const visibleIds = useMemo(() => new Set(visible.map(item => String(item.id))),[visible])
  useEffect(() => {
    setShownCount(CATALOG_PAGE_SIZE)
  },[filters,preferences.work_location,preferences.max_commute_minutes])

  const personalScores = useMemo(() => new Map(
    (response?.items ?? []).map(item => [String(item.apartment_id),item.score] as const)
  ),[response])
  const districtCards = useMemo(() => districts.map(name => {
    const group = items.filter(x => x.district.name === name)
    const scores = group.map(item => {
      const personal = personalScores.get(String(item.id))
      if (typeof personal === 'number' && Number.isFinite(personal)) return personal
      const fallback = item.recommendation.score
      if (fallback === null || !Number.isFinite(fallback)) return null
      return fallback > 10 ? fallback/10 : fallback
    }).filter((value):value is number => value !== null)
    return {
      name,
      count:group.length,
      score:scores.length ? scores.reduce((sum,value) => sum+value,0)/scores.length : 0,
      photo:group[0]?.photos[0]?.url,
      description:group[0]?.district.description
    }
  }).sort((a,b) => b.score-a.score).slice(0,3),[items,districts,personalScores])

  function change<K extends keyof CatalogFilters>(key:K,value:CatalogFilters[K]) {
    setFilter(key,value)
  }

  function reset() {
    resetFilters()
    setParams({})
  }

  function search(e:React.FormEvent) {
    e.preventDefault()
    setParams(filters.query ? { q:filters.query } : {})
  }

  function setDistrict(name:string) {
    change('district',filters.district === name ? '' : name)
  }

  function pickDistrict(name:string) {
    setDistrict(name)
    document.getElementById('catalog')?.scrollIntoView({behavior:'smooth',block:'start'})
  }

  function startWorkPick() {
    setWorkPicking(true)
    setFiltersOpen(false)
    requestAnimationFrame(() => document.getElementById('main-map')?.scrollIntoView({ behavior:'smooth', block:'center' }))
  }

  function chooseWorkLocation(location:{ lat:number; lon:number }) {
    setWorkLocation(location)
  }

  async function recommend(value:RecommendationRequest) {
    const sequence=++requestSequence.current
    setRecommendationLoading(true)
    setRecommendationError('')
    try {
      const result = await api.recommend({...value,catalog_filters:filters})
      if (sequence === requestSequence.current) setResponse(result)
      return true
    } catch(e) {
      if (sequence === requestSequence.current) setRecommendationError(e instanceof Error ? e.message : 'Не удалось подобрать квартиры')
      return false
    } finally {
      if (sequence === requestSequence.current) setRecommendationLoading(false)
    }
  }

  async function apply() {
    const invalid = validatePreferences(preferences)
    if (invalid) {
      setValidationError(invalid)
      return false
    }
    setValidationError('')
    const ok=await recommend(preferences)
    if (!ok) return false
    document.getElementById('recommendations')?.scrollIntoView({behavior:'smooth',block:'start'})
    return true
  }

  function resetPreferences() {
    reset()
    resetPreferencesState()
    setValidationError('')

  }

  function saveCurrentSearch() {
    const parts=[
      filters.district || 'Красноярск',
      filters.rooms ? (filters.rooms >= 4 ? '4+ комн.' : filters.rooms === -1 ? 'Студия' : `${filters.rooms} комн.`) : '',
      filters.maxPrice ? `до ${Math.round(filters.maxPrice/1_000_000*10)/10} млн` : ''
    ].filter(Boolean)
    createSavedSearch({
      label:parts.join(' · '),
      preferences,
      filters,
      items
    })
    setSavedSearchMessage(`Поиск сохранён. Сейчас ему соответствуют ${visible.length} квартир.`)
    window.setTimeout(() => setSavedSearchMessage(''),3200)
  }

  const activeCount = Number(!!filters.dealType)+Number(!!filters.district)+Number(!!filters.maxPrice)+Number(!!filters.rooms)+Number(!!filters.minArea)+Number(!!filters.yearFrom)+Number(!!filters.buildingType)+Number(filters.onlyWithPhotos)
  const filterChips = [
    filters.dealType ? {key:'dealType',label:filters.dealType === 'rent' ? 'Аренда' : 'Продажа',clear:() => change('dealType','')} : null,
    filters.district ? { key:'district',label:`Район: ${filters.district}`,clear:() => change('district','') } : null,
    filters.maxPrice ? { key:'maxPrice',label:`До ${new Intl.NumberFormat('ru-RU').format(filters.maxPrice)} ₽`,clear:() => change('maxPrice',0) } : null,
    filters.rooms ? { key:'rooms',label:filters.rooms >= 4 ? '4+ комнаты' : filters.rooms === -1 ? 'Студия' : `${filters.rooms} комн.`,clear:() => change('rooms',0) } : null,
    filters.minArea ? { key:'minArea',label:`От ${filters.minArea} м²`,clear:() => change('minArea',0) } : null,
    filters.yearFrom ? { key:'yearFrom',label:`Дом от ${filters.yearFrom}`,clear:() => change('yearFrom',0) } : null,
    filters.buildingType ? { key:'buildingType',label:filters.buildingType,clear:() => change('buildingType','') } : null,
    filters.onlyWithPhotos ? { key:'onlyWithPhotos',label:'Только с фото',clear:() => change('onlyWithPhotos',false) } : null
  ].filter((chip):chip is { key:string;label:string;clear:()=>void } => chip !== null)

  return <div className="dashboard-page">
    <div className="shell dashboard-grid">
      <PreferencePanel
        value={preferences}
        onChange={setPreferences}
        onApply={apply}
        busy={recommendationLoading}
        error={validationError}
        filters={filters}
        districts={districts}
        buildingTypes={buildingTypes}
        onFilter={change}
        onReset={resetPreferences}
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        workPicking={workPicking}
        onStartWorkPick={startWorkPick}
      />
      <div className="dashboard-main">
        <Reveal className="dashboard-intro">
          <div>
            <span className="dashboard-kicker">GEODOM · АНАЛИЗ ГОРОДСКОЙ СРЕДЫ</span>
            <h1>Выберите квартиру <em>с пониманием района</em></h1>
            <p>Укажите бюджет, семью и важные для вас факторы. Изучите персональный подбор, инфраструктуру и планы развития.</p>
          </div>
          <div className="intro-badge">
            <span className="intro-badge-icon"><Building2 size={22}/></span>
            <div><b>{KRASNOYARSK_DISTRICTS.length} районов</b><small>для осознанного выбора</small></div>
            <ArrowUpRight size={16}/>
          </div>
          <Suspense fallback={null}><CitySignal/></Suspense>
        </Reveal>

        <form className="dashboard-search" onSubmit={search}>
          <Search size={19}/>
          <input aria-label="Поиск по району или адресу" value={filters.query} onChange={e => change('query',e.target.value)} placeholder="Поиск по району, улице или адресу…"/>
          <button type="submit">Найти <ArrowRight size={16}/></button>
        </form>
        {filterChips.length > 0 && <div className="active-filter-chips" aria-label="Активные фильтры">
          {filterChips.map(chip => <button type="button" key={chip.key} onClick={chip.clear}>{chip.label}<span aria-hidden="true">×</span></button>)}
          <button type="button" className="clear-all" onClick={reset}>Сбросить всё</button>
        </div>}

        <Reveal delay={.08}>
        <div className="map-panel" id="main-map">
          <div className="map-topbar">
            <div><span className="map-tab active"><MapPin size={16}/> Яндекс Карта</span><span className="map-tab secondary">Красноярск и районы</span></div>
            <div className="map-topbar-note"><span className="pulse-dot"/> {workPicking ? 'Выберите место работы' : `${visible.length} квартир по вашим параметрам`}</div>
          </div>
          {savedSearchMessage && <div className="saved-search-toast"><BellRing size={14}/>{savedSearchMessage}</div>}
          {loading
            ? <PageLoading/>
            : error
              ? <EmptyState title="Карта недоступна" message={error}/>
              : <MapPanel
                  items={visible}
                  geoObjects={geoObjects}
                  activeApartmentIds={visibleIds}
                  scoreByApartment={personalScores}
                  selectedDistrict={filters.district}
                  onDistrict={setDistrict}
                  workLocation={preferences.work_location}
                  workPicking={workPicking}
                  onWorkLocation={chooseWorkLocation}
                />}
          <div className="map-caption"><CircleHelp size={15}/> Приблизьте карту, чтобы увидеть объекты рядом с квартирами.{geoError ? ' Не удалось загрузить объекты рядом.' : ''} <span>© Яндекс · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></span></div>
        </div>
        </Reveal>

        <Reveal delay={.04}><RecommendationResults response={response ? {...response,items:response.items.filter(item => visibleIds.has(String(item.apartment_id)))} : null} loading={recommendationLoading} error={recommendationError} onRetry={() => { void recommend(preferences) }}/></Reveal>

        <Reveal>
        <div className="dashboard-section-title">
          <div><h2>Районы <span>Красноярска</span></h2><p>Обзор квартир и инфраструктуры по районам</p></div>
          <Link className="districts-all-link" to="/districts">Все 7 районов <ArrowRight size={14}/></Link>
        </div>
        <div className="district-cards">{districtCards.map((d,i) => <button className={`district-card ${filters.district === d.name ? 'chosen' : ''}`} key={d.name} onClick={() => pickDistrict(d.name)}>
          <div className="district-image">{d.photo && <img src={d.photo} alt=""/>}<span>{i === 0 ? '✦ Высокая оценка' : `${d.count} предложений`}</span></div>
          <div className="district-card-head"><h3>{d.name}</h3><b><Sparkles size={16}/>{d.score.toFixed(1)} <small>/ 10</small></b></div>
          <p>{d.description}</p>
          <div className="district-card-bottom">Смотреть квартиры <ArrowRight size={16}/></div>
        </button>)}</div>
        </Reveal>

        <Reveal>
        {promotedApartments.length > 0 && <section className="sponsored-section" aria-label="Продвигаемые объявления">
          <div className="sponsored-heading"><div><span>ПЛАТНОЕ ПРОДВИЖЕНИЕ</span><h2>Продвигаемые объявления</h2></div><small>Позиция здесь не меняет персональный score</small></div>
          <div className="card-grid">{promotedApartments.map((item,index) => <ApartmentCard item={item} index={index} promoted key={item.id}/>)}</div>
        </section>}
        <section className="listings-section" id="catalog">
          <div className="dashboard-section-title listings-title">
            <div><h2>Все <span>квартиры</span></h2><p>{loading ? 'Загружаем предложения…' : `${visible.length} предложений · показано ${Math.min(shownCount,visible.length)}`}</p></div>
            <div className="listings-actions">
              {user
                ? <button type="button" className="save-search-button" onClick={saveCurrentSearch}><BellRing size={15}/> Сохранить поиск</button>
                : <Link className="save-search-button" to="/login?next=/"><BellRing size={15}/> Сохранить поиск</Link>}
              <button className="mobile-filter-button" onClick={() => setFiltersOpen(true)}><SlidersHorizontal size={17}/> Параметры {activeCount > 0 && <b>{activeCount}</b>}</button>
              <label htmlFor="sort">Сортировка</label>
              <div className="select-wrap">
                <select id="sort" value={filters.sort} onChange={e => change('sort',e.target.value as CatalogSort)}>
                  <option value="recommended">По оценке</option>
                  <option value="price_asc">Цена ↑</option>
                  <option value="price_desc">Цена ↓</option>
                  <option value="area_desc">Площадь ↓</option>
                </select>
                <ChevronDown size={15}/>
              </div>
            </div>
          </div>
          {loading
            ? <PageLoading/>
            : error
              ? <EmptyState title="Не удалось загрузить квартиры" message={error} action={<button className="button dark" onClick={() => window.location.reload()}>Повторить</button>}/>
              : visible.length
                ? <>
                    <div className="card-grid">{shownApartments.map((item,index) => <ApartmentCard item={item} index={index} key={item.id}/>)}</div>
                    {shownCount < visible.length && <div className="catalog-load-more">
                      <button type="button" className="button light" onClick={() => setShownCount(count => count+CATALOG_PAGE_SIZE)}>Показать ещё {Math.min(CATALOG_PAGE_SIZE,visible.length-shownCount)}</button>
                      <span>{shownCount} / {visible.length}</span>
                    </div>}
                  </>
                : <EmptyState title="Ничего не нашлось" message="Попробуйте расширить бюджет или выбрать другой район." action={<button className="button dark" onClick={reset}>Сбросить фильтры</button>}/>}
        </section>
        </Reveal>

        <div className="dashboard-end">
          <span><Sparkles size={18}/> ГеоДом помогает смотреть дальше квартиры</span>
          <Link to="/register">Разместить своё объявление <ArrowRight size={17}/></Link>
        </div>
      </div>
    </div>
  </div>
}
