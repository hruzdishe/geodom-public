import { ArrowUpRight, Heart, MapPin, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Apartment } from '../types'
import { area, price } from '../lib/catalog'
import { useGeoDomStore } from '../store/useGeoDomStore'
import { resolvePhotoUrl } from '../lib/media'
export function ApartmentCard({ item, index = 0, promoted = false }: { item: Apartment; index?: number; promoted?: boolean }) {
  const coverPhoto = item.photos.find(x => x.is_cover) || item.photos[0]
  const cover = coverPhoto ? resolvePhotoUrl(coverPhoto) : null
  const savedIds = useGeoDomStore(state => state.savedIds)
  const toggleSaved = useGeoDomStore(state => state.toggleSaved)
  const saved = savedIds.includes(item.id)
  const photoCount = item.photo_count ?? item.photos.length
  return <article className="home-card" style={{ animationDelay: `${index * 60}ms` }}>
    <button type="button" className={`card-like ${saved ? 'saved' : ''}`} aria-label={saved ? 'Убрать квартиру из сохранённого' : 'Сохранить квартиру'} onClick={() => toggleSaved(item.id)}><Heart size={18} fill={saved ? 'currentColor' : 'none'}/></button>
    <Link to={`/apartments/${item.id}`} className="home-card-link">
      <div className="home-card-image">{cover ? <img src={cover} alt={item.title} loading="lazy" /> : <div className="image-placeholder">GEODOM</div>}{promoted && <span className="promoted-label">Продвижение</span>}<span className="photo-count">{photoCount ? `01 / ${String(photoCount).padStart(2, '0')}` : 'БЕЗ ФОТО'}</span></div>
      <div className="home-card-info"><div className="card-price">{price(item.price)}{item.deal_type === 'rent' ? item.rent_period === 'day' ? ' / сутки' : ' / месяц' : ''} <ArrowUpRight size={19}/></div><h3>{item.title}</h3><div className="card-address"><MapPin size={14}/>{item.address}</div><div className="card-bottom"><span>{item.rooms === 0 ? 'Студия' : `${item.rooms}-комн.`}</span><span>{area(item.area)}</span><span>{item.floor} / {item.total_floors} эт.</span></div>{item.recommendation.score !== null && <div className="card-match"><Sparkles size={14}/> Обзорная оценка {(item.recommendation.score > 10 ? item.recommendation.score/10 : item.recommendation.score).toFixed(1)}/10 <small>{item.recommendation.ml_available ? 'ML' : 'демо'}</small></div>}</div>
    </Link>
    {item.source_url && <a className="card-source-link" href={item.source_url} target="_blank" rel="noopener noreferrer">Оригинальное объявление <ArrowUpRight size={13}/></a>}
  </article>
}
export function EmptyState({ title, message, action }: { title: string; message: string; action?: React.ReactNode }) { return <div className="empty-state"><span className="empty-mark">✳</span><h2>{title}</h2><p>{message}</p>{action}</div> }
export function PageLoading() { return <div className="page-loading"><span className="spinner"/>Загружаем данные…</div> }
