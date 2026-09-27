import { distance } from '../lib/catalog'
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowLeft, ArrowUpRight, GitCompareArrows, MapPin, Sparkles, Trash2, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { area, price } from '../lib/catalog'
import { loadLastRecommendation } from '../lib/recommendations'
import { resolvePhotoUrl } from '../lib/media'
import { useGeoDomStore } from '../store/useGeoDomStore'
import type { Apartment, RecommendationItem } from '../types'

type DetailState = {
  id:string
  apartment:Apartment|null
  error:string
}

const factorRows:Array<{ key:keyof RecommendationItem['scores'];label:string }> = [
  { key:'schools',label:'Школы' },
  { key:'parks',label:'Парки' },
  { key:'transport',label:'Транспорт' },
  { key:'ecology',label:'Экология' },
  { key:'safety',label:'Безопасность' },
  { key:'commute',label:'Дорога до работы' },
  { key:'price',label:'Цена / бюджет' }
]

function roomsLabel(value:number) {
  return value === 0 ? 'Студия' : `${value}-комн.`
}

export function Compare() {
  const comparedIds=useGeoDomStore(state => state.comparedIds)
  const toggleCompared=useGeoDomStore(state => state.toggleCompared)
  const clearCompared=useGeoDomStore(state => state.clearCompared)
  const [details,setDetails]=useState<DetailState[]>([])
  const [loading,setLoading]=useState(false)
  const recommendation=loadLastRecommendation()

  const recommendationById=useMemo(
    () => new Map((recommendation?.items ?? []).map(item => [String(item.apartment_id),item] as const)),
    [recommendation]
  )

  useEffect(() => {
    let cancelled=false
    if (!comparedIds.length) {
      setDetails([])
      return
    }

    setLoading(true)
    Promise.all(comparedIds.map(async id => {
      try {
        const apartment=await api.detail(id)
        return { id,apartment,error:'' }
      } catch(error) {
        return {
          id,
          apartment:null,
          error:error instanceof Error ? error.message : 'Не удалось загрузить квартиру'
        }
      }
    })).then(result => {
      if (!cancelled) setDetails(result)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => { cancelled=true }
  },[comparedIds.join('|')])

  if (!comparedIds.length) {
    return <div className="shell compare-page">
      <Link to="/#recommendations" className="back-link"><ArrowLeft size={17}/> К подбору</Link>
      <div className="compare-empty-page">
        <GitCompareArrows size={38}/>
        <span>СРАВНЕНИЕ</span>
        <h1>Добавьте 2–3 квартиры</h1>
        <p>Сравнение теперь открывается отдельной страницей и не перекрывает карту, каталог или карточки.</p>
        <Link className="button dark" to="/#recommendations">Выбрать варианты</Link>
      </div>
    </div>
  }

  return <div className="shell compare-page">
    <div className="compare-page-toolbar">
      <Link to="/#recommendations" className="back-link"><ArrowLeft size={17}/> Назад к подбору</Link>
      <button type="button" className="compare-clear-all" onClick={clearCompared}><Trash2 size={15}/> Очистить сравнение</button>
    </div>

    <header className="compare-page-head">
      <div>
        <span>GEODOM / СРАВНЕНИЕ</span>
        <h1>Сравнение квартир</h1>
        <p>{comparedIds.length} из 3 вариантов. Таблица использует последнюю персональную выдачу и данные карточек.</p>
      </div>
      <div className="compare-page-count"><b>{comparedIds.length}</b><span>/ 3</span></div>
    </header>

    {loading && <div className="compare-page-loading"><span className="spinner"/> Загружаем карточки…</div>}

    <div className="compare-scroll">
      <div className="compare-matrix" style={{ '--compare-count':Math.max(2,comparedIds.length) } as CSSProperties}>
        <div className="compare-label-cell compare-sticky-label">Объект</div>
        {comparedIds.map(id => {
          const state=details.find(item => item.id === id)
          const apartment=state?.apartment
          const recommendationItem=recommendationById.get(id)
          const cover=apartment?.photos.find(photo => photo.is_cover) || apartment?.photos[0]
          const coverUrl=cover ? resolvePhotoUrl(cover) : recommendationItem?.cover_image_url || null
          return <div className="compare-object-card" key={id}>
            <button className="compare-page-remove" type="button" onClick={() => toggleCompared(id)} aria-label="Убрать из сравнения"><X size={14}/></button>
            <Link to={`/apartments/${id}`} className="compare-object-image">
              {coverUrl ? <img src={coverUrl} alt={apartment?.title || recommendationItem?.title || 'Квартира'} loading="lazy"/> : <div className="image-placeholder">GEODOM</div>}
            </Link>
            <div>
              {recommendationItem && <span className="compare-object-score"><Sparkles size={14}/> {(recommendationItem.score?.toFixed(1) ?? '—')} / 10</span>}
              <Link to={`/apartments/${id}`} className="compare-object-title">{apartment?.title || recommendationItem?.title || `Квартира ${id}`} <ArrowUpRight size={14}/></Link>
              {state?.error && <small className="compare-object-error">{state.error}</small>}
            </div>
          </div>
        })}

        <CompareRow label="Цена" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          const item=recommendationById.get(id)
          return price(apartment?.price ?? item?.price ?? 0)
        }}/>
        <CompareRow label="Цена за м²" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          const item=recommendationById.get(id)
          const value=item?.price_m2 || (apartment && apartment.area > 0 ? apartment.price/apartment.area : 0)
          return value ? `${price(Math.round(value))} / м²` : '—'
        }}/>
        <CompareRow label="Комнаты" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? roomsLabel(apartment.rooms) : '—'
        }}/>
        <CompareRow label="Площадь" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? area(apartment.area) : '—'
        }}/>
        <CompareRow label="Этаж" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? `${apartment.floor} / ${apartment.total_floors}` : '—'
        }}/>
        <CompareRow label="Район" ids={comparedIds} render={id => details.find(item => item.id === id)?.apartment?.district.name || '—'}/>
        <CompareRow label="Адрес" ids={comparedIds} wrap render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? <span className="compare-address"><MapPin size={13}/>{apartment.address}</span> : '—'
        }}/>
        <CompareRow label="Дом / год" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          if (!apartment) return '—'
          return [apartment.building_type,apartment.building_year].filter(Boolean).join(' · ') || '—'
        }}/>
        <CompareRow label="Ремонт" ids={comparedIds} render={id => details.find(item => item.id === id)?.apartment?.renovation || '—'}/>
        <CompareRow label="Источник" ids={comparedIds} wrap render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment?.source_url
            ? <a className="compare-source-link" href={apartment.source_url} target="_blank" rel="noopener noreferrer">{apartment.upstream_source?.toLowerCase() === 'sibdom' ? 'СИБДОМ' : apartment.upstream_source || 'Оригинал'} <ArrowUpRight size={13}/></a>
            : '—'
        }}/>

        <div className="compare-section-row">Персональные факторы</div>
        {factorRows.map(({key,label}) => <CompareRow key={key} label={label} ids={comparedIds} render={id => {
          const item=recommendationById.get(id)
          return item?.scores[key] == null ? '—' : `${item.scores[key]!.toFixed(1)} / 10`
        }}/>)}

        <div className="compare-section-row">Инфраструктура</div>
        <CompareRow label="Школы до 1 км" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? String(apartment.features.schools_1km ?? '—') : '—'
        }}/>
        <CompareRow label="Парки до 1 км" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? String(apartment.features.parks_1km ?? '—') : '—'
        }}/>
        <CompareRow label="Ближайшая школа" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? distance(apartment.features.nearest_school_m) : '—'
        }}/>
        <CompareRow label="Ближайший парк" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? distance(apartment.features.nearest_park_m) : '—'
        }}/>
        <CompareRow label="Транспорт" ids={comparedIds} render={id => {
          const apartment=details.find(item => item.id === id)?.apartment
          return apartment ? distance(apartment.features.nearest_transport_m) : '—'
        }}/>
      </div>
    </div>

    <p className="compare-page-note">«—» означает, что значение не пришло или не рассчитано. Мы не подменяем отсутствие данных нулём.</p>
  </div>
}

function CompareRow({
  label,
  ids,
  render,
  wrap=false
}:{
  label:string
  ids:string[]
  render:(id:string)=>ReactNode
  wrap?:boolean
}) {
  return <>
    <div className="compare-label-cell">{label}</div>
    {ids.map(id => <div className={`compare-value-cell ${wrap ? 'wrap' : ''}`} key={`${label}:${id}`}>{render(id)}</div>)}
  </>
}
