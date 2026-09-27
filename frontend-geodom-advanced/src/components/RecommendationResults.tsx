import { useEffect, useRef } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight, Bookmark, Check, CircleAlert, FileText, GitCompareArrows, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { userFacingWarnings } from '../lib/recommendationWarnings'
import { api } from '../lib/api'
import { useGeoDomStore } from '../store/useGeoDomStore'
import { price } from '../lib/catalog'
import { localCoverForApartmentId } from '../lib/media'
import type { InteractionEvent, RecommendationItem, RecommendationResponse } from '../types'

const dimensions: Array<{ key:keyof RecommendationItem['scores']; label:string }> = [
  { key:'schools',label:'Школы' }, { key:'parks',label:'Парки' }, { key:'transport',label:'Транспорт' },
  { key:'ecology',label:'Экология' }, { key:'safety',label:'Безопасность' }
]
const contributionLabels: Record<keyof RecommendationItem['scores'],string> = {
  schools:'Школы и семья',
  parks:'Парки',
  transport:'Транспорт',
  ecology:'Экология',
  safety:'Безопасность',
  commute:'Дорога до работы',
  price:'Цена и бюджет'
}
function scoreContributions(item: RecommendationItem) {
  return Object.entries(item.contributions ?? {})
    .flatMap(([key,value]) => typeof value === 'number' && Number.isFinite(value) ? [[key as keyof RecommendationItem['scores'],value] as const] : [])
    .sort((a,b) => b[1]-a[1])
}
export function RecommendationResults({ response, loading, error, onRetry }:{ response:RecommendationResponse|null; loading:boolean; error:string; onRetry:()=>void }) {
  const saved = useGeoDomStore(state => state.savedIds)
  const compared = useGeoDomStore(state => state.comparedIds)
  const toggleSaved = useGeoDomStore(state => state.toggleSaved)
  const toggleCompared = useGeoDomStore(state => state.toggleCompared)
  const sent = useRef(new Set<string>())
  function track(event:InteractionEvent,item:RecommendationItem,position:number) {
    if (!response) return
    const key = `${response.request_id}:${event}:${item.apartment_id}`
    if (event === 'impression' && sent.current.has(key)) return
    sent.current.add(key)
    void api.event({ request_id:response.request_id,event,entity_type:'apartment',entity_id:item.apartment_id,position }).catch(() => {})
  }
  function save(item:RecommendationItem,position:number) { const active = toggleSaved(String(item.apartment_id)); if (active) track('save',item,position) }
  function compare(item:RecommendationItem,position:number) {
    const id=String(item.apartment_id)
    const wasCompared=compared.includes(id)
    const active=toggleCompared(id)
    if (!wasCompared && active) track('compare',item,position)
  }
  return <section className="recommendations-section" id="recommendations"><div className="dashboard-section-title recommendation-title"><div><h2>Подбор <span>для вас</span></h2><p>Квартиры по вашим параметрам и приоритетам</p></div>{response && <div className="recommendation-head-actions"><span className="mini-label">{response.items.length} ВАРИАНТОВ</span><Link className="report-link" to="/report"><FileText size={15}/> Отчёт</Link></div>}</div>
    {loading ? <div className="recommendation-loading"><span className="spinner"/> Подбираем варианты под ваши параметры…</div> : error ? <div className="recommendation-error"><CircleAlert size={20}/><div><b>Не удалось получить рекомендации</b><p>{error}. Общий каталог ниже доступен.</p></div><button onClick={onRetry}>Повторить</button></div> : response && <>
      {userFacingWarnings(response.warnings).length > 0 && <div className="recommendation-warning"><CircleAlert size={19}/><div>{userFacingWarnings(response.warnings).map(w => <p key={w}>{w}</p>)}</div></div>}
      {response.items.length ? <div className="recommendation-grid">{response.items.map((item,index) => <RecommendationCard key={String(item.apartment_id)} item={item} position={index+1} saved={saved.includes(String(item.apartment_id))} compared={compared.includes(String(item.apartment_id))} compareFull={compared.length >= 3} onImpression={() => track('impression',item,index+1)} onOpen={() => track('click',item,index+1)} onSave={() => save(item,index+1)} onCompare={() => compare(item,index+1)}/>)}</div> : <div className="recommendation-empty"><h3>По этим параметрам квартир нет</h3><p>Измените бюджет, число комнат или время до работы.</p></div>}
      <div className="recommendation-meta-row">

        {compared.length > 0 && <Link className="compare-page-cta" to="/compare"><GitCompareArrows size={15}/> Открыть сравнение <b>{compared.length}</b></Link>}
      </div>
    </>}
  </section>
}
function RecommendationCard({item,position,saved,compared,compareFull,onImpression,onOpen,onSave,onCompare}:{ item:RecommendationItem;position:number;saved:boolean;compared:boolean;compareFull:boolean;onImpression:()=>void;onOpen:()=>void;onSave:()=>void;onCompare:()=>void }) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const node=ref.current; if (!node) return
    if (!('IntersectionObserver' in window)) { onImpression(); return }
    const observer=new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { onImpression(); observer.disconnect() } },{ threshold:.35 })
    observer.observe(node); return () => observer.disconnect()
  },[onImpression])
  const contributions = scoreContributions(item)
  const reduceMotion = useReducedMotion()
  const cover = item.cover_image_url || localCoverForApartmentId(item.apartment_id)
  return <motion.article ref={ref} className="recommendation-card" layout={!reduceMotion} transition={{ layout:{ duration:.34,ease:[.22,1,.36,1] } }}><Link to={`/apartments/${item.apartment_id}`} onClick={onOpen} className="recommendation-cover">{cover ? <img src={cover} alt={item.title} loading="lazy"/> : <div className="image-placeholder">GEODOM</div>}<span className="recommendation-rank">#{position} В ПОДБОРКЕ</span></Link><div className="recommendation-body"><div className="recommendation-score-row"><span className="recommendation-score"><Sparkles size={15}/> {(item.score?.toFixed(1) ?? '—')} <small>/ 10</small></span><span className="score-caption">СООТВЕТСТВИЕ</span></div><Link to={`/apartments/${item.apartment_id}`} onClick={onOpen} className="recommendation-title">{item.title} <ArrowUpRight size={17}/></Link><div className="recommendation-price">{price(item.price)} <small>{price(item.price_m2)} / м²</small></div>{item.commute_minutes !== null && <p className="commute-estimate" title="По прямой, при скорости 30 км/ч">До работы ≈ {Math.ceil(item.commute_minutes)} мин</p>}<ul className="reason-list">{item.reasons.slice(0,2).map(reason => <li key={reason}><Check size={14}/>{reason}</li>)}</ul><div className="mini-scores">{dimensions.slice(0,3).map(({key,label}) => <div key={key}><span>{label}</span><div><i style={{width:`${(item.scores[key] || 0)*10}%`}}/></div><b>{item.scores[key]?.toFixed(1) ?? '—'}</b></div>)}</div>{contributions.length > 0 && <details className="score-explanation"><summary>Что повлияло на оценку</summary><div>{contributions.slice(0,5).map(([key,value]) => <span key={key}><b>{contributionLabels[key]}</b><em>+{value.toFixed(1)}</em></span>)}</div></details>}{userFacingWarnings(item.warnings).length > 0 && <div className="card-warning">{userFacingWarnings(item.warnings).join(' · ')}</div>}<div className="recommendation-actions"><button onClick={onSave} className={saved ? 'active' : ''} aria-label={saved ? 'Убрать из сохранённого' : 'Сохранить квартиру'}><Bookmark size={16} fill={saved?'currentColor':'none'}/>{saved?'Сохранено':'Сохранить'}</button><button onClick={onCompare} className={compared?'active':''} disabled={compareFull&&!compared} aria-label={compared?'Убрать из сравнения':'Добавить к сравнению'}><GitCompareArrows size={16}/>{compared?'В сравнении':'Сравнить'}</button></div></div></motion.article>
}
