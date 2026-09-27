import { useEffect,useMemo,useState } from 'react'
import { BadgeCheck, BarChart3, Building2, Check, Crown, LockKeyhole, Megaphone, Phone, Target, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api,isDemo } from '../lib/api'
import { price } from '../lib/catalog'
import { DEMO_PRO_LEADS,leadAnalytics,loadLeadPipeline,loadPromotedIds,matchLeadToApartment,savePromotedIds,setLeadStage,type LeadStage,type ProLead } from '../lib/pro'
import { loadSharedDemandProfile,sharedDemandProfileToLead } from '../lib/demandProfile'
import { EmptyState,PageLoading } from '../components/Ui'
import type { Apartment } from '../types'

type ProTab='crm'|'promotion'|'developer'|'analytics'

export function Pro() {
  const [tab,setTab]=useState<ProTab>('crm')
  const [mine,setMine]=useState<Apartment[]>([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [selectedId,setSelectedId]=useState('')
  const [promoted,setPromoted]=useState<string[]>(loadPromotedIds)
  const [unlocked,setUnlocked]=useState<string[]>([])
  const [pipeline,setPipeline]=useState<Record<string,LeadStage>>(loadLeadPipeline)
  const [stageFilter,setStageFilter]=useState<'all'|LeadStage>('all')
  const sharedProfile=useMemo(() => loadSharedDemandProfile(),[])
  const crmLeads=useMemo(() => {
    if (!isDemo) return []
    return sharedProfile?.consentToContact
      ? [sharedDemandProfileToLead(sharedProfile),...DEMO_PRO_LEADS]
      : DEMO_PRO_LEADS
  },[sharedProfile])

  useEffect(() => {
    api.mine()
      .then(items => {
        setMine(items.filter(item => item.status !== 'deleted'))
        setSelectedId(items[0]?.id || '')
      })
      .catch(error => setError(error instanceof Error ? error.message : 'Не удалось загрузить объявления'))
      .finally(() => setLoading(false))
  },[])

  const selected=mine.find(item => item.id === selectedId) ?? mine[0] ?? null
  const matches=useMemo(() => selected
    ? crmLeads
        .map(lead => matchLeadToApartment(lead,selected))
        .filter(match => match.lead.intent === 'buy')
        .filter(match => stageFilter === 'all' || (pipeline[match.lead.id] || 'new') === stageFilter)
        .sort((a,b) => b.score-a.score)
    : [],[selected,crmLeads,stageFilter,pipeline])
  const analytics=useMemo(() => leadAnalytics(DEMO_PRO_LEADS),[])

  function togglePromotion(id:string) {
    const next=promoted.includes(id) ? promoted.filter(item => item !== id) : [...promoted,id]
    setPromoted(next)
    savePromotedIds(next)
  }

  function unlock(lead:ProLead) {
    if (!lead.consentToContact) return
    setUnlocked(current => current.includes(lead.id) ? current : [...current,lead.id])
  }

  function updateStage(leadId:string,stage:LeadStage) {
    setPipeline(setLeadStage(leadId,stage))
  }

  const stageCounts=useMemo(() => {
    const counts:Record<LeadStage,number>={ new:0,contacted:0,viewing:0,won:0,lost:0 }
    for (const lead of crmLeads.filter(item => item.intent === 'buy')) counts[pipeline[lead.id] || 'new']++
    return counts
  },[crmLeads,pipeline])

  return <div className="pro-page">
    <div className="shell">
      <header className="pro-hero">
        <div>
          <span><Crown size={15}/> GEODOM PRO · FRONTEND DEMO</span>
          <h1>CRM, лиды, продвижение и аналитика спроса</h1>
          <p>Рабочий прототип B2B-модели. Здесь нет реальных платежей и реальных пользовательских контактов: лиды ниже синтетические, а контакт открывается только когда у лида стоит согласие.</p>
        </div>
        <div className="pro-hero-metrics">
          <div><small>CRM-лидов</small><b>{crmLeads.length}</b></div>
          <div><small>Покупка</small><b>{analytics.buyLeads}</b></div>
          <div><small>Аренда</small><b>{analytics.rentLeads}</b></div>
        </div>
      </header>

      <nav className="pro-tabs" aria-label="GeoDom Pro">
        <button className={tab === 'crm' ? 'active' : ''} onClick={() => setTab('crm')}><Users size={15}/> CRM и лиды</button>
        <button className={tab === 'promotion' ? 'active' : ''} onClick={() => setTab('promotion')}><Megaphone size={15}/> Продвижение</button>
        <button className={tab === 'developer' ? 'active' : ''} onClick={() => setTab('developer')}><Building2 size={15}/> Застройщикам</button>
        <button className={tab === 'analytics' ? 'active' : ''} onClick={() => setTab('analytics')}><BarChart3 size={15}/> Analytics</button>
      </nav>

      {tab === 'crm' && <section className="pro-workspace">
        <div className="pro-section-head">
          <div><span>01 / КВАЛИФИЦИРОВАННЫЕ ЛИДЫ</span><h2>Кому подходит ваше объявление</h2><p>Match считается по бюджету, району, комнатности и части инфраструктурных приоритетов. В production сюда добавятся commute и полный recommendation profile.</p></div>
          <div className="pro-lead-price"><small>Модель монетизации</small><b>500–3 000 ₽</b><span>за квалифицированный лид</span></div>
        </div>

        {loading ? <PageLoading/> : error ? <EmptyState title="CRM недоступна" message={error}/> : !mine.length ? <EmptyState title="Нет своих объявлений" message="Добавьте квартиру, чтобы увидеть matching лидов." action={<Link className="button dark" to="/new">Добавить объявление</Link>}/> : <>
          <div className="pro-crm-controls">
            <label className="pro-property-select">Объявление
              <select value={selected?.id || ''} onChange={event => setSelectedId(event.target.value)}>
                {mine.map(item => <option key={item.id} value={item.id}>{item.title} · {price(item.price)}</option>)}
              </select>
            </label>
            <label className="pro-stage-filter">Этап CRM
              <select value={stageFilter} onChange={event => setStageFilter(event.target.value as 'all'|LeadStage)}>
                <option value="all">Все лиды</option>
                <option value="new">Новые · {stageCounts.new}</option>
                <option value="contacted">Связались · {stageCounts.contacted}</option>
                <option value="viewing">Просмотр · {stageCounts.viewing}</option>
                <option value="won">Сделка · {stageCounts.won}</option>
                <option value="lost">Неактуально · {stageCounts.lost}</option>
              </select>
            </label>
          </div>

          <div className="pro-pipeline-summary">
            <span><b>{stageCounts.new}</b> новые</span>
            <span><b>{stageCounts.contacted}</b> связались</span>
            <span><b>{stageCounts.viewing}</b> просмотр</span>
            <span><b>{stageCounts.won}</b> сделка</span>
            <span><b>{stageCounts.lost}</b> неактуально</span>
          </div>

          <div className="pro-leads">
            {matches.map(match => <article key={match.lead.id} className="pro-lead-card">
              <div className="pro-lead-avatar">{match.lead.name.slice(0,1)}</div>
              <div className="pro-lead-main">
                <div className="pro-lead-title"><h3>{match.lead.name}</h3><span>{match.score}% match</span>{match.lead.source === 'local' && <em>Согласованный профиль</em>}</div>
                <p>{match.lead.intent === 'buy' ? `Покупка до ${price(match.lead.budgetMax)}` : `Аренда до ${price(match.lead.monthlyRentMax || 0)}/мес`} · {match.lead.roomsMin}–{match.lead.roomsMax} комн. · {match.lead.districts.length ? match.lead.districts.join(', ') : 'любой район'}</p>
                <div className="pro-lead-tags">{match.lead.priorities.map(priority => <span key={priority}>{priority}</span>)}</div>
                <small>Работа: {match.lead.workLabel} · commute до {match.lead.maxCommuteMinutes} мин</small>
                <div className="pro-match-reasons">{match.reasons.length ? match.reasons.map(reason => <span key={reason}><Check size={11}/>{reason}</span>) : <span>Совпадений по объявлению пока мало</span>}</div>
              </div>
              <div className="pro-lead-contact">
                <label className="lead-stage-select">Этап
                  <select value={pipeline[match.lead.id] || 'new'} onChange={event => updateStage(match.lead.id,event.target.value as LeadStage)}>
                    <option value="new">Новый</option>
                    <option value="contacted">Связались</option>
                    <option value="viewing">Просмотр</option>
                    <option value="won">Сделка</option>
                    <option value="lost">Неактуально</option>
                  </select>
                </label>
                {!match.lead.consentToContact ? <><LockKeyhole size={18}/><b>Контакт закрыт</b><small>Нет согласия пользователя на передачу контакта</small></>
                  : unlocked.includes(match.lead.id) ? <><Phone size={18}/><b>{match.lead.contact}</b><small>{match.lead.source === 'local' ? 'Контакт из согласованного профиля этого браузера' : 'Демо-контакт · не реальный номер'}</small></>
                    : <><LockKeyhole size={18}/><b>Контакт доступен Pro</b><button type="button" onClick={() => unlock(match.lead)}>Открыть контакт</button></>}
              </div>
            </article>)}
          </div>
        </>}
      </section>}

      {tab === 'promotion' && <section className="pro-workspace">
        <div className="pro-section-head"><div><span>02 / ПРОДВИЖЕНИЕ</span><h2>Платное выделение без подмены score</h2><p>Продвижение создаёт отдельный маркированный рекламный слот. Оно не изменяет персональную оценку квартиры и не маскируется под органическую рекомендацию.</p></div></div>
        {loading ? <PageLoading/> : !mine.length ? <EmptyState title="Продвигать пока нечего" message="Сначала создайте объявление." action={<Link className="button dark" to="/new">Добавить квартиру</Link>}/> : <div className="pro-promotion-list">
          {mine.map(item => {
            const active=promoted.includes(item.id)
            return <article key={item.id}>
              <div><span className={`promotion-status ${active ? 'active' : ''}`}>{active ? 'Продвижение включено' : 'Обычная выдача'}</span><h3>{item.title}</h3><p>{item.address} · {price(item.price)}</p></div>
              <div className="promotion-actions"><small>Демо-тариф: 490 ₽ / 7 дней</small><button type="button" className={active ? 'active' : ''} onClick={() => togglePromotion(item.id)}>{active ? 'Отключить' : 'Продвинуть'}</button></div>
            </article>
          })}
        </div>}
      </section>}

      {tab === 'developer' && <section className="pro-workspace">
        <div className="pro-section-head"><div><span>03 / B2B ДЛЯ ЗАСТРОЙЩИКА</span><h2>Страница ЖК + спрос + лиды + продвижение</h2><p>Frontend-концепт кабинета застройщика. Цифры ниже рассчитаны на синтетическом demo-demand и не являются статистикой реального рынка.</p></div></div>
        <div className="developer-demo-card">
          <div className="developer-demo-name"><span className="developer-building"><Building2/></span><div><span>ДЕМО ЖК</span><h3>ЖК «Енисейский»</h3><p>Советский район · 126 квартир</p></div><BadgeCheck size={22}/></div>
          <div className="developer-demo-metrics">
            <div><small>Потенциальных лидов</small><b>{DEMO_PRO_LEADS.filter(lead => lead.districts.includes('Советский')).length}</b><span>в demo-demand</span></div>
            <div><small>Медианный бюджет</small><b>{price(analytics.medianBudget)}</b></div>
            <div><small>Главный фактор</small><b>{analytics.topPriorities[0]?.[0] || '—'}</b></div>
          </div>
          <div className="developer-feature-grid">
            {['Подтверждённый застройщик','Страница ЖК и квартир','Квалифицированные лиды','Продвижение объектов','Аналитика спроса','Сравнение с конкурентами'].map(feature => <span key={feature}><Check size={13}/>{feature}</span>)}
          </div>
        </div>
      </section>}

      {tab === 'analytics' && <section className="pro-workspace">
        <div className="pro-section-head"><div><span>04 / GEODOM ANALYTICS</span><h2>Что ищут и что влияет на выбор</h2><p>Агрегированный demo-demand. Контакты пользователей в Analytics не выводятся.</p></div></div>
        <div className="analytics-summary">
          <div><Target/><small>Медианный бюджет покупки</small><b>{price(analytics.medianBudget)}</b></div>
          <div><Users/><small>Профилей спроса</small><b>{analytics.leads}</b></div>
          <div><BarChart3/><small>Доля покупки</small><b>{Math.round(analytics.buyLeads/analytics.leads*100)}%</b></div>
        </div>
        <div className="analytics-columns">
          <div><h3>Где ищут</h3>{analytics.topDistricts.map(([name,count]) => <div className="analytics-row" key={name}><span>{name}</span><b>{count}</b><i style={{width:`${count/analytics.leads*100}%`}}/></div>)}</div>
          <div><h3>Что важно</h3>{analytics.topPriorities.map(([name,count]) => <div className="analytics-row" key={name}><span>{name}</span><b>{count}</b><i style={{width:`${count/analytics.leads*100}%`}}/></div>)}</div>
        </div>
        <div className="analytics-privacy-note"><LockKeyhole size={15}/><span>Production Analytics должен работать на агрегированных/de-identified данных и не раскрывать конкретные профили пользователей малым когортам.</span></div>
      </section>}
    </div>
  </div>
}
