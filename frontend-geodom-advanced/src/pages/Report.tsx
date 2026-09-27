import { userFacingWarnings } from '../lib/recommendationWarnings'
import { useEffect } from 'react'
import { ArrowLeft, CircleAlert, FileText, MapPin, Printer, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { price } from '../lib/catalog'
import { loadLastRecommendation } from '../lib/recommendations'
import { useGeoDomStore } from '../store/useGeoDomStore'
import type { RecommendationItem } from '../types'

const factorLabels: Record<keyof RecommendationItem['scores'],string> = {
  schools:'Школы',
  parks:'Парки',
  transport:'Транспорт',
  ecology:'Экология',
  safety:'Безопасность',
  commute:'Дорога до работы',
  price:'Цена'
}

function familyLabel(adults:number,children:number) {
  const child = children === 0 ? 'без детей' : children === 1 ? '1 ребёнок' : children < 5 ? `${children} ребёнка` : `${children} детей`
  return `${adults} взр. · ${child}`
}

export function Report() {
  const preferences = useGeoDomStore(state => state.preferences)
  const response = loadLastRecommendation()
  const top = response?.items.slice(0,3) ?? []

  useEffect(() => {
    const first=response?.items[0]
    if (!response || !first) return
    void api.event({
      request_id:response.request_id,
      event:'report',
      entity_type:'apartment',
      entity_id:first.apartment_id,
      position:1
    }).catch(() => {})
  },[response?.request_id])

  function printReport() {
    window.print()
  }

  if (!response) {
    return <div className="shell report-page">
      <Link to="/" className="back-link"><ArrowLeft size={17}/> К подбору</Link>
      <div className="report-empty">
        <FileText size={34}/>
        <h1>Сначала соберите подбор</h1>
        <p>Подберите квартиры, чтобы сохранить или распечатать результат.</p>
        <Link className="button dark" to="/#recommendations">Перейти к подбору</Link>
      </div>
    </div>
  }

  return <div className="shell report-page">
    <div className="report-toolbar">
      <Link to="/#recommendations" className="back-link"><ArrowLeft size={17}/> Вернуться к подбору</Link>
      <button className="button dark" onClick={printReport}><Printer size={17}/> Печать / PDF</button>
    </div>

    <header className="report-header">
      <div><span>GEODOM / ПЕРСОНАЛЬНЫЙ ОТЧЁТ</span><h1>Короткий список для решения</h1><p>Снимок последнего успешного подбора. Значения отражают выбранные параметры и доступные данные.</p></div>

    </header>

    <section className="report-parameters">
      <div><small>Бюджет</small><b>{price(preferences.budget_max)}</b></div>
      <div><small>Первоначальный взнос</small><b>{price(preferences.down_payment)}</b></div>
      <div><small>Семья</small><b>{familyLabel(preferences.family.adults,preferences.family.children)}</b></div>
      <div><small>Работа</small><b>{preferences.work_location ? <><MapPin size={14}/> {preferences.work_location.lat.toFixed(4)}, {preferences.work_location.lon.toFixed(4)}</> : 'Не выбрана'}</b></div>
      <div><small>Макс. время в пути</small><b>{preferences.max_commute_minutes} мин</b></div>
    </section>

    {userFacingWarnings(response.warnings).length > 0 && <div className="report-warning"><CircleAlert size={19}/><div><b>Ограничения данных</b>{userFacingWarnings(response.warnings).map(warning => <p key={warning}>{warning}</p>)}</div></div>}

    <section className="report-section">
      <div className="report-section-head"><div><span>01</span><h2>Топ вариантов</h2></div><small>{top.length} из {response.items.length} вариантов</small></div>
      <div className="report-candidates">{top.map((item,index) => <article key={String(item.apartment_id)}>
        <div className="report-rank">#{index+1}</div>
        <div className="report-candidate-main"><span>ПЕРСОНАЛЬНЫЙ SCORE</span><h3>{item.title}</h3><strong>{price(item.price)}</strong><p>{item.reasons.slice(0,2).join(' · ') || 'Причины рекомендации не переданы'}</p></div>
        <div className="report-score"><Sparkles size={16}/><b>{(item.score?.toFixed(1) ?? '—')}</b><small>/ 10</small></div>
      </article>)}</div>
    </section>

    <section className="report-section">
      <div className="report-section-head"><div><span>02</span><h2>Факторы</h2></div><small>оценки 0–10</small></div>
      <div className="report-factor-table">
        <div className="report-factor-row header"><span>Фактор</span>{top.map((item,index) => <b key={String(item.apartment_id)}>#{index+1}</b>)}</div>
        {(Object.keys(factorLabels) as Array<keyof RecommendationItem['scores']>).map(key => <div className="report-factor-row" key={key}>
          <span>{factorLabels[key]}</span>
          {top.map(item => <b key={String(item.apartment_id)}>{item.scores[key]?.toFixed(1) ?? '—'}</b>)}
        </div>)}
      </div>
    </section>


  </div>
}
