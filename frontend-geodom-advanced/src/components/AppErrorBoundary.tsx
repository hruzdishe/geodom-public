import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props {
  children:ReactNode
}

interface State {
  error:Error|null
}

export class AppErrorBoundary extends Component<Props,State> {
  state:State = { error:null }

  static getDerivedStateFromError(error:Error):State {
    return { error }
  }

  componentDidCatch(error:Error,info:ErrorInfo) {
    console.error('GeoDom UI error',error,info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return <div className="shell fatal-state" role="alert">
      <AlertTriangle size={32}/>
      <span>ИНТЕРФЕЙС ВОССТАНОВЛЕН</span>
      <h1>Этот экран не удалось отрисовать</h1>
      <p>{this.state.error.message || 'Произошла непредвиденная ошибка интерфейса.'}</p>
      <div>
        <button className="button dark" onClick={() => window.location.reload()}><RotateCcw size={17}/> Перезагрузить</button>
        <Link className="button light" to="/">На главную</Link>
      </div>
    </div>
  }
}
