import { ArrowRight, MapPin, RotateCcw, Trash2, X } from 'lucide-react'
import type { CatalogFilters, RecommendationRequest } from '../types'

const priorities: Array<{ key:keyof RecommendationRequest['priorities']; label:string }> = [
  { key:'schools', label:'Школы' }, { key:'parks', label:'Парки' }, { key:'transport', label:'Транспорт' }
]

function workLabel(location: RecommendationRequest['work_location']) {
  if (!location) return 'Выбрать точку на карте'
  return `${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}`
}

export function PreferencePanel({
  value,
  onChange,
  onApply,
  busy,
  error,
  filters,
  districts,
  buildingTypes,
  onFilter,
  onReset,
  open,
  onClose,
  workPicking,
  onStartWorkPick
}:{
  value:RecommendationRequest
  onChange:(value:RecommendationRequest)=>void
  onApply:()=>Promise<boolean>
  busy:boolean
  error:string
  filters:CatalogFilters
  districts:string[]
  buildingTypes:string[]
  onFilter:<K extends keyof CatalogFilters>(key:K,value:CatalogFilters[K])=>void
  onReset:()=>void
  open:boolean
  onClose:()=>void
  workPicking:boolean
  onStartWorkPick:()=>void
}) {
  return <aside className={`dashboard-sidebar preferences-sidebar ${open ? 'open' : ''}`}>
    <div className="sidebar-heading">
      <h2>Ваши параметры</h2>
      <button type="button" onClick={onReset}>Сбросить</button>
      <button type="button" className="mobile-only-close" onClick={onClose} aria-label="Закрыть параметры"><X size={19}/></button>
    </div>
    <form onSubmit={e => { e.preventDefault(); void onApply().then(ok => { if (ok) onClose() }) }}>
      <div className="sidebar-block">
        <label className="sidebar-label" htmlFor="budget-max">Бюджет покупки, ₽</label>
        <input id="budget-max" type="number" inputMode="numeric" min="1" step="1" value={value.budget_max || ''} onChange={e => onChange({...value,budget_max:e.target.value === '' ? 0 : Number(e.target.value)})} required/>
        <div className="money-preview">{value.budget_max > 0 ? new Intl.NumberFormat('ru-RU').format(value.budget_max) + ' ₽' : 'Введите любую сумму'}</div>
        <label className="sidebar-label inline" htmlFor="down-payment">Первоначальный взнос, ₽</label>
        <input id="down-payment" type="number" inputMode="numeric" min="0" step="1" value={value.down_payment || ''} onChange={e => onChange({...value,down_payment:e.target.value === '' ? 0 : Number(e.target.value)})}/>
        <div className="money-preview">{value.down_payment > 0 ? new Intl.NumberFormat('ru-RU').format(value.down_payment) + ' ₽' : 'Без первоначального взноса'}</div>
      </div>

      <div className="sidebar-block">
        <span className="sidebar-label">Состав семьи</span>
        <div className="family-grid">
          <label>Взрослых<select value={value.family.adults} aria-label="Количество взрослых" onChange={e => onChange({...value,family:{...value.family,adults:Number(e.target.value)}})}>{[1,2,3,4].map(n => <option key={n}>{n}</option>)}</select></label>
          <label>Детей<select value={value.family.children} aria-label="Количество детей" onChange={e => onChange({...value,family:{...value.family,children:Number(e.target.value)}})}>{[0,1,2,3,4].map(n => <option key={n}>{n}</option>)}</select></label>
        </div>
      </div>

      <div className="sidebar-block">
        <span className="sidebar-label">Место работы</span>
        <div className={`work-location-control ${workPicking ? 'picking' : ''}`}>
          <button type="button" className="work-location-pick" onClick={onStartWorkPick}>
            <MapPin size={16}/>
            <span><b>{workPicking ? 'Кликните по карте…' : workLabel(value.work_location)}</b><small>{value.work_location ? 'Точку можно перетащить на карте' : 'Укажите место работы на карте'}</small></span>
          </button>
          {value.work_location && <button type="button" className="work-location-clear" aria-label="Удалить место работы" onClick={() => onChange({...value,work_location:null})}><Trash2 size={15}/></button>}
        </div>
        <label className="sidebar-label inline" htmlFor="commute">До работы, примерно</label>
        <select id="commute" disabled={!value.work_location} title="По прямой, при скорости 30 км/ч" value={value.max_commute_minutes} onChange={e => onChange({...value,max_commute_minutes:Number(e.target.value)})}>{[10,20,30,40,60,90].map(n => <option key={n} value={n}>До {n} минут</option>)}</select>
      </div>

      <div className="sidebar-block">
        <label className="sidebar-label" htmlFor="deal-filter">Тип сделки</label>
        <select id="deal-filter" value={filters.dealType ?? ''} onChange={e => onFilter('dealType',e.target.value === 'sale' ? 'sale' : e.target.value === 'rent' ? 'rent' : '')}><option value="">Все предложения</option><option value="sale">Продажа</option><option value="rent">Аренда</option></select>
        {filters.dealType === 'rent' && <><label className="sidebar-label inline" htmlFor="rent-filter">Период аренды</label><select id="rent-filter" value={filters.rentPeriod ?? ''} onChange={e => onFilter('rentPeriod',e.target.value === 'day' ? 'day' : e.target.value === 'month' ? 'month' : '')}><option value="">Любой</option><option value="month">Месяц</option><option value="day">Сутки</option></select></>}
        <label className="sidebar-label inline" htmlFor="catalog-price">Цена до, ₽</label><input id="catalog-price" type="number" min="0" value={filters.maxPrice || ''} onChange={e => onFilter('maxPrice',Number(e.target.value))}/>
        <label className="sidebar-label inline" htmlFor="district">Район</label>
        <select id="district" value={filters.district} onChange={e => onFilter('district',e.target.value)}><option value="">Все районы</option>{districts.map(d => <option key={d}>{d}</option>)}</select>
        <span className="sidebar-label inline">Количество комнат</span>
        <div className="room-options">{[[0,'Все'],[-1,'Студия'],[1,'1'],[2,'2'],[3,'3'],[4,'4+']].map(([n,label]) => <button type="button" key={n} className={filters.rooms === n ? 'selected' : ''} onClick={() => onFilter('rooms',Number(n))}>{label}</button>)}</div>

        <div className="catalog-extra-filters">
          <label>
            <span>Площадь от, м²</span>
            <input type="number" min="0" step="1" value={filters.minArea || ''} onChange={e => onFilter('minArea',e.target.value === '' ? 0 : Number(e.target.value))}/>
          </label>
          <label>
            <span>Год дома от</span>
            <input type="number" min="1800" max="2100" step="1" value={filters.yearFrom || ''} onChange={e => onFilter('yearFrom',e.target.value === '' ? 0 : Number(e.target.value))}/>
          </label>
        </div>

        <label className="sidebar-label inline" htmlFor="building-type">Тип дома</label>
        <select id="building-type" value={filters.buildingType} onChange={e => onFilter('buildingType',e.target.value)}>
          <option value="">Любой тип</option>
          {buildingTypes.map(type => <option key={type} value={type}>{type}</option>)}
        </select>

        <label className="photo-filter-toggle">
          <input type="checkbox" checked={filters.onlyWithPhotos} onChange={e => onFilter('onlyWithPhotos',e.target.checked)}/>
          <span>Только квартиры с фотографиями</span>
        </label>
      </div>

      <div className="sidebar-block priority-block">
        <span className="sidebar-label">Ваши приоритеты <small>1–5</small></span>
        <p>Вес факторов для персональной рекомендации</p>
        <div className="priority-sliders">{priorities.map(({key,label}) => <label key={key} className="priority-slider"><span>{label}<b>{value.priorities[key]}</b></span><input type="range" min="1" max="5" value={value.priorities[key]} aria-label={`Приоритет: ${label}`} onChange={e => onChange({...value,priorities:{...value.priorities,[key]:Number(e.target.value)}})}/></label>)}</div>
      </div>

      {error && <div className="sidebar-error" role="alert">{error}</div>}
      <button className="sidebar-apply" type="submit" disabled={busy}>{busy ? 'Подбираем…' : 'Подобрать жильё'} <ArrowRight size={18}/></button>
      <button className="sidebar-reset" type="button" onClick={onReset}><RotateCcw size={15}/> Сбросить параметры</button>
    </form>
  </aside>
}
