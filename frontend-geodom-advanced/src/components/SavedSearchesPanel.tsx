import { useMemo,useState } from 'react'
import { ArrowRight, BellRing, Check, Search, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  deleteSavedSearch,
  loadSavedSearches,
  markSavedSearchSeen,
  savedSearchMatches,
  savedSearchNewMatches,
  type SavedSearch
} from '../lib/savedSearches'
import { useGeoDomStore } from '../store/useGeoDomStore'
import type { Apartment } from '../types'

function summary(search:SavedSearch) {
  const parts:string[]=[]
  if (search.filters.district) parts.push(search.filters.district)
  if (search.filters.rooms) parts.push(search.filters.rooms >= 4 ? '4+ комн.' : `${search.filters.rooms} комн.`)
  if (search.filters.maxPrice) parts.push(`до ${new Intl.NumberFormat('ru-RU').format(search.filters.maxPrice)} ₽`)
  if (search.filters.minArea) parts.push(`от ${search.filters.minArea} м²`)
  if (search.filters.onlyWithPhotos) parts.push('с фото')
  return parts.length ? parts.join(' · ') : 'Все квартиры по текущему профилю'
}

export function SavedSearchesPanel({ items }:{ items:Apartment[] }) {
  const [searches,setSearches]=useState(loadSavedSearches)
  const setPreferences=useGeoDomStore(state => state.setPreferences)
  const replaceFilters=useGeoDomStore(state => state.replaceFilters)
  const navigate=useNavigate()

  const rows=useMemo(() => searches.map(search => ({
    search,
    matches:savedSearchMatches(search,items),
    fresh:savedSearchNewMatches(search,items)
  })),[searches,items])

  function restore(search:SavedSearch) {
    setPreferences(search.preferences)
    replaceFilters(search.filters)
    navigate('/#catalog')
  }

  function markSeen(search:SavedSearch) {
    setSearches(markSavedSearchSeen(search.id,items))
  }

  function remove(search:SavedSearch) {
    setSearches(deleteSavedSearch(search.id))
  }

  return <section className="saved-searches-panel">
    <div className="saved-searches-head">
      <span><BellRing size={19}/></span>
      <div><small>СОХРАНЁННЫЕ ПОИСКИ</small><h2>Новые квартиры по вашим условиям</h2><p>GeoDom сравнивает текущий каталог со снимком на момент сохранения поиска. В demo уведомления считаются локально при открытии кабинета.</p></div>
      <b>{rows.reduce((sum,row) => sum+row.fresh.length,0)} новых</b>
    </div>

    {rows.length ? <div className="saved-search-list">{rows.map(({search,matches,fresh}) => <article key={search.id}>
      <div className="saved-search-icon"><Search size={17}/></div>
      <div className="saved-search-copy">
        <div><h3>{search.label}</h3>{fresh.length > 0 && <span>{fresh.length} новых</span>}</div>
        <p>{summary(search)}</p>
        <small>{matches.length} совпадений сейчас · сохранён {new Date(search.createdAt).toLocaleDateString('ru-RU')}</small>
      </div>
      <div className="saved-search-actions">
        <button type="button" className="saved-search-open" onClick={() => restore(search)}>Открыть <ArrowRight size={14}/></button>
        {fresh.length > 0 && <button type="button" onClick={() => markSeen(search)}><Check size={14}/> Просмотрено</button>}
        <button type="button" className="danger" aria-label={`Удалить поиск ${search.label}`} onClick={() => remove(search)}><Trash2 size={14}/></button>
      </div>
    </article>)}</div> : <div className="saved-search-empty">Сохраните поиск из каталога — здесь появится его состояние и новые совпадения.</div>}
  </section>
}
