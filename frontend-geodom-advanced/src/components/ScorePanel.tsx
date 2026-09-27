import { userFacingWarnings } from '../lib/recommendationWarnings'
import { Check, CircleAlert, Sparkles } from 'lucide-react'
import { getLastRecommendationItem } from '../lib/recommendations'
import { price } from '../lib/catalog'
import type { Apartment, RecommendationItem } from '../types'
const dimensions: Array<{ key:keyof RecommendationItem['scores']; label:string }> = [
  { key:'schools',label:'Школы' },{ key:'parks',label:'Парки' },{ key:'transport',label:'Транспорт' },
  { key:'ecology',label:'Экология' },{ key:'safety',label:'Безопасность' }
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
export function ScorePanel({ apartment }:{ apartment:Apartment }) {
  const personal = getLastRecommendationItem(apartment.id)
  const fallback = apartment.recommendation
  const score = personal ? personal.item.score : fallback.score === null ? null : fallback.score > 10 ? fallback.score / 10 : fallback.score
  const reasons = personal?.item.reasons || fallback.reasons
  const warnings = personal ? [...personal.response.warnings,...personal.item.warnings] : fallback.warning ? [fallback.warning] : []
  const contributions = personal
    ? Object.entries(personal.item.contributions ?? {})
      .flatMap(([key,value]) => typeof value === 'number' && Number.isFinite(value) ? [[key as keyof RecommendationItem['scores'],value] as const] : [])
      .sort((a,b) => b[1]-a[1])
    : []
  return <div className="score-panel"><span className="panel-eyebrow"><Sparkles size={16}/> {personal ? 'ПЕРСОНАЛЬНАЯ ОЦЕНКА' : 'ОЦЕНКА КВАРТИРЫ'}</span>
    {score !== null ? <><div className="score-main"><b>{score.toFixed(1)}</b><span>/ 10</span></div><div className="score-track"><span style={{width:`${Math.max(0,Math.min(100,score*10))}%`}}/></div><p>Почему этот вариант интересен:</p><ul>{reasons.map(reason => <li key={reason}><Check size={16}/>{reason}</li>)}</ul></> : <><h3>Оценка готовится</h3><p>Запустите подбор в каталоге, чтобы увидеть персональную оценку.</p></>}
    {personal && <div className="detail-sub-scores">{dimensions.filter(({key}) => personal.item.scores[key] !== null).map(({key,label}) => <div key={key}><span>{label}</span><b>{personal.item.scores[key]?.toFixed(1) ?? 'нет данных'}</b></div>)}</div>}
    {contributions.length > 0 && <div className="detail-contributions"><span>Вклад факторов</span>{contributions.map(([key,value]) => <div key={key}><b>{contributionLabels[key]}</b><em>+{value.toFixed(1)}</em></div>)}</div>}
    {personal?.item.predicted_price_m2 != null && <div className="predicted-price"><span>Оценка модели за м²</span><b>{price(personal.item.predicted_price_m2)}</b><small>Это прогноз модели, не гарантированная рыночная цена.</small></div>}
    {personal?.item.commute_minutes != null && <p title="По прямой, при скорости 30 км/ч">До работы ≈ {Math.ceil(personal.item.commute_minutes)} мин</p>}
    {userFacingWarnings(warnings).length > 0 && <div className="detail-score-warnings"><CircleAlert size={16}/><div>{userFacingWarnings(warnings).map(warning => <p key={warning}>{warning}</p>)}</div></div>}
  </div>
}
