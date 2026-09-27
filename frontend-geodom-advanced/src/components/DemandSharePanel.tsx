import { useEffect,useMemo,useState } from 'react'
import { Check, RefreshCw, ShieldCheck, UserRoundSearch, X } from 'lucide-react'
import { api,isDemo } from '../lib/api'
import {
  buildSharedDemandProfile,
  clearSharedDemandProfile,
  loadSharedDemandProfile,
  revokeSharedDemandProfile,
  saveSharedDemandProfile,
  type SharedDemandProfile
} from '../lib/demandProfile'
import { useGeoDomStore } from '../store/useGeoDomStore'

export function DemandSharePanel() {
  const user=useGeoDomStore(state => state.user)
  const preferences=useGeoDomStore(state => state.preferences)
  const filters=useGeoDomStore(state => state.filters)
  const initial=useMemo(() => {
    if (!isDemo) return null
    const profile=loadSharedDemandProfile()
    return profile && profile.userId === user?.id ? profile : null
  },[user?.id])
  const [profile,setProfile]=useState<SharedDemandProfile|null>(initial)
  const [contact,setContact]=useState(initial?.contact || '')
  const [consent,setConsent]=useState(Boolean(initial?.consentToContact))
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)

  useEffect(() => {
    if (isDemo || !user) return
    let cancelled=false
    setBusy(true)
    api.demandProfile()
      .then(next => {
        if (cancelled) return
        setProfile(next)
        setContact(next?.contact || '')
        setConsent(Boolean(next?.consentToContact))
      })
      .catch(error => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : 'Не удалось загрузить профиль поиска.')
      })
      .finally(() => { if (!cancelled) setBusy(false) })
    return () => { cancelled=true }
  },[user?.id])

  if (!user) return null
  const currentUser=user

  async function save() {
    if (contact.trim().length < 3) {
      setMessage('Укажите телефон, Telegram или email для связи.')
      return
    }
    const next=buildSharedDemandProfile({
      current:profile,
      user:currentUser,
      contact,
      consentToContact:consent,
      preferences,
      filters
    })
    setBusy(true)
    try {
      if (isDemo) {
        saveSharedDemandProfile(next)
        setProfile(next)
      } else {
        setProfile(await api.saveDemandProfile(next))
      }
      setMessage(consent
        ? 'Профиль поиска обновлён. Контакт доступен только подходящим Pro-риелторам.'
        : 'Профиль сохранён, но передача контакта выключена.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось сохранить профиль поиска.')
    } finally {
      setBusy(false)
    }
  }

  async function revoke() {
    setBusy(true)
    try {
      if (isDemo) {
        const next=revokeSharedDemandProfile()
        if (next && next.userId === currentUser.id) setProfile(next)
      } else if (profile) {
        const next={...profile,consentToContact:false,updatedAt:new Date().toISOString()}
        setProfile(await api.saveDemandProfile(next))
      }
      setConsent(false)
      setMessage('Согласие на передачу контакта отозвано.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось отозвать согласие.')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      if (isDemo) clearSharedDemandProfile()
      else await api.deleteDemandProfile()
      setProfile(null)
      setContact('')
      setConsent(false)
      setMessage('Профиль поиска удалён.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось удалить профиль поиска.')
    } finally {
      setBusy(false)
    }
  }

  const district=filters.district || 'Любой район'
  const rooms=!filters.rooms ? 'Любая комнатность' : filters.rooms >= 4 ? '4+ комнат' : `${filters.rooms} комн.`
  const active=profile?.consentToContact === true

  return <section className="demand-share-panel">
    <div className="demand-share-head">
      <span><UserRoundSearch size={19}/></span>
      <div>
        <small>МОЙ ПОИСК → GEODOM PRO</small>
        <h2>Получать предложения только по вашему сценарию</h2>
        <p>GeoDom передаёт контакт только когда пользователь явно разрешил связь. Согласие можно отозвать или удалить вместе с профилем поиска.</p>
      </div>
      <div className={`demand-share-status ${active ? 'active' : ''}`}>{active ? <><Check size={14}/> Доступен Pro</> : <><ShieldCheck size={14}/> Контакт закрыт</>}</div>
    </div>

    <div className="demand-share-snapshot">
      <div><span>Бюджет</span><b>{new Intl.NumberFormat('ru-RU').format(preferences.budget_max)} ₽</b></div>
      <div><span>Район</span><b>{district}</b></div>
      <div><span>Комнаты</span><b>{rooms}</b></div>
      <div><span>До работы</span><b>до {preferences.max_commute_minutes} мин</b></div>
    </div>

    <div className="demand-share-form">
      <label>
        <span>Контакт для подходящих риелторов</span>
        <input value={contact} disabled={busy} onChange={event => setContact(event.target.value)} placeholder="+7…, @telegram или email"/>
      </label>
      <label className="demand-consent">
        <input type="checkbox" disabled={busy} checked={consent} onChange={event => setConsent(event.target.checked)}/>
        <span><b>Разрешаю передавать этот контакт подходящим Pro-риелторам</b><small>Без галочки контакт не попадает в выдачу лидов.</small></span>
      </label>
    </div>

    <div className="demand-share-actions">
      <button type="button" className="button dark" disabled={busy} onClick={() => void save()}><RefreshCw size={15}/> {busy ? 'Сохраняем…' : profile ? 'Обновить профиль поиска' : 'Сохранить профиль поиска'}</button>
      {profile?.consentToContact && <button type="button" className="button light" disabled={busy} onClick={() => void revoke()}><ShieldCheck size={15}/> Отозвать согласие</button>}
      {profile && <button type="button" className="demand-delete" disabled={busy} onClick={() => void remove()}><X size={15}/> Удалить профиль</button>}
    </div>

    {message && <div className="demand-share-message">{message}</div>}
    <p className="demand-share-footnote">{isDemo
      ? 'Demo хранит профиль локально в браузере.'
      : 'Live mode хранит профиль на backend. Контакт выдаётся Pro только при активном согласии.'}</p>
  </section>
}
