import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { ArrowUpRight, GitCompareArrows, House, Menu, Plus, X } from 'lucide-react'
import { api, isDemo } from './lib/api'
import { PageLoading } from './components/Ui'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { PageTransition } from './components/MotionPrimitives'
import { useGeoDomStore } from './store/useGeoDomStore'
import './styles.css'

const Catalog = lazy(() => import('./pages/Catalog').then(module => ({ default:module.Catalog })))
const Detail = lazy(() => import('./pages/Detail').then(module => ({ default:module.Detail })))
const Auth = lazy(() => import('./pages/Auth').then(module => ({ default:module.Auth })))
const Account = lazy(() => import('./pages/Account').then(module => ({ default:module.Account })))
const ListingForm = lazy(() => import('./pages/ListingForm').then(module => ({ default:module.ListingForm })))
const Report = lazy(() => import('./pages/Report').then(module => ({ default:module.Report })))
const Compare = lazy(() => import('./pages/Compare').then(module => ({ default:module.Compare })))
const Districts = lazy(() => import('./pages/Districts').then(module => ({ default:module.Districts })))
const Pro = lazy(() => import('./pages/Pro').then(module => ({ default:module.Pro })))

function Header() {
  const user = useGeoDomStore(state => state.user)
  const comparedCount = useGeoDomStore(state => state.comparedIds.length)
  const [open,setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setOpen(false),[location.pathname])

  useEffect(() => {
    if (!open) return
    const previous=document.body.style.overflow
    document.body.style.overflow='hidden'
    const onKeyDown=(event:KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown',onKeyDown)
    return () => {
      document.body.style.overflow=previous
      window.removeEventListener('keydown',onKeyDown)
    }
  },[open])

  const close=() => setOpen(false)

  return <>
    <header className="site-header">
      <div className="shell header-inner">
        <Link to="/" className="brand" aria-label="ГеоДом — главная">
          <span className="brand-symbol"><House size={25} strokeWidth={2.8}/></span>
          <span className="brand-name">ГеоДом<span className="brand-label">где лучше жить</span></span>
        </Link>
        <nav className="desktop-nav" aria-label="Основная навигация">
          <a href="/#recommendations">Подбор</a><Link to="/districts">Районы</Link><a href="/#main-map">Карта</a><a href="/#catalog">Квартиры</a>
          <Link to="/compare" className={comparedCount ? 'nav-compare active' : 'nav-compare'}><GitCompareArrows size={14}/> Сравнение{comparedCount ? <b>{comparedCount}</b> : null}</Link>
          <Link to="/report">Отчёт</Link>
        </nav>
        <div className="header-actions">
          <Link className="post-link" to={user ? '/new' : '/login?next=/new'}><Plus size={18}/> Разместить квартиру</Link>
          <Link className="account-link" to={user ? '/account' : '/login'}>{user ? <><span className="user-dot">{user.login[0].toUpperCase()}</span><span>Кабинет</span></> : 'Войти'}<ArrowUpRight size={15}/></Link>
        </div>
        <button className="mobile-menu" aria-label={open ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(value => !value)}>{open ? <X/> : <Menu/>}</button>
      </div>
    </header>
    {open && <>
      <button type="button" className="mobile-panel-backdrop" aria-label="Закрыть меню" onClick={close}/>
      <nav className="mobile-panel" id="mobile-navigation" aria-label="Мобильная навигация">
        <div className="mobile-panel-primary">
          <a href="/#recommendations" onClick={close}>Подбор</a>
          <Link to="/districts" onClick={close}>Районы</Link>
          <a href="/#main-map" onClick={close}>Карта</a>
          <a href="/#catalog" onClick={close}>Квартиры</a>
          <Link to="/compare" onClick={close}>Сравнение{comparedCount ? ` · ${comparedCount}` : ''}</Link>
          <Link to="/report" onClick={close}>Отчёт</Link>
        </div>
        <div className="mobile-panel-actions">
          <Link className="mobile-panel-post" to={user ? '/new' : '/login?next=/new'} onClick={close}><Plus size={17}/> Разместить квартиру</Link>
          <Link className="mobile-panel-account" to={user ? '/account' : '/login'} onClick={close}>{user ? 'Личный кабинет' : 'Войти'}<ArrowUpRight size={16}/></Link>
        </div>
      </nav>
    </>}
  </>
}
function Footer() { return <footer className="site-footer"><div className="shell footer-inner"><div><Link className="footer-brand" to="/">ГеоДом<span>°</span></Link><p>Квартиры и городская среда<br/>в одном месте.</p></div><div className="footer-right"><span>КРАСНОЯРСК · 2026</span><p>Информация о демо-объектах приведена для проверки интерфейса. Уточняйте сведения из официальных источников.</p></div></div></footer> }
function RequireAuth({ children }: { children: React.ReactNode }) { const user = useGeoDomStore(state => state.user); const ready = useGeoDomStore(state => state.authReady); const location = useLocation(); return !ready ? <PageLoading/> : user ? children : <NavigateToLogin next={location.pathname}/> }
function NavigateToLogin({ next }: { next: string }) { const navigate = useNavigate(); useEffect(() => { navigate(`/login?next=${encodeURIComponent(next)}`, { replace:true }) }, [navigate, next]); return null }
export default function App() {
  const setUser = useGeoDomStore(state => state.setUser)
  const [authError,setAuthError] = useState('')
  const setAuthReady = useGeoDomStore(state => state.setAuthReady)
  useEffect(() => {
    const sessionUser = api.session()?.user
    if (sessionUser) setUser(sessionUser)
    api.currentUser().then(setUser).catch(error => { setUser(null); setAuthError(error.message) }).finally(() => setAuthReady(true))
  }, [setUser,setAuthReady])
  return <div className="app"><Header/>{isDemo && <div className="demo-banner"><span className="shell">ДЕМО-РЕЖИМ <span>·</span> Примерные квартиры и проекты. Для реальных данных подключите FastAPI.</span></div>}<main>{authError && <div className="form-error" role="alert">{authError} <button onClick={() => window.location.reload()}>Повторить</button></div>}<AppErrorBoundary><Suspense fallback={<PageLoading/>}><Routes><Route path="/" element={<PageTransition><Catalog/></PageTransition>}/><Route path="/apartments/:id" element={<PageTransition><Detail/></PageTransition>}/><Route path="/login" element={<PageTransition><Auth mode="login"/></PageTransition>}/><Route path="/register" element={<PageTransition><Auth mode="register"/></PageTransition>}/><Route path="/account" element={<RequireAuth><PageTransition><Account/></PageTransition></RequireAuth>}/><Route path="/report" element={<PageTransition><Report/></PageTransition>}/><Route path="/compare" element={<PageTransition><Compare/></PageTransition>}/><Route path="/districts" element={<PageTransition><Districts/></PageTransition>}/><Route path="/pro" element={<RequireAuth><PageTransition>{isDemo ? <Pro/> : <div className="shell form-page"><h1>GeoDom Pro</h1><p>Этот раздел пока недоступен.</p><Link to="/account">В личный кабинет</Link></div>}</PageTransition></RequireAuth>}/><Route path="/new" element={<RequireAuth><PageTransition><ListingForm/></PageTransition></RequireAuth>}/><Route path="/apartments/:id/edit" element={<RequireAuth><PageTransition><ListingForm/></PageTransition></RequireAuth>}/><Route path="*" element={<PageTransition><div className="shell not-found"><span>404</span><h1>Такой страницы нет</h1><Link className="button dark" to="/">Вернуться к квартирам</Link></div></PageTransition>}/></Routes></Suspense></AppErrorBoundary></main><Footer/></div>
}
