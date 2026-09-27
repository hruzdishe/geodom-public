import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { migrateLegacyStorage } from './lib/storage'
migrateLegacyStorage()
ReactDOM.createRoot(document.getElementById('root')!).render(<BrowserRouter><App/></BrowserRouter>)
