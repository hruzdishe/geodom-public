let loader: Promise<any> | null = null

type YandexWindow = Window & { ymaps?: any }

export function loadYandexMaps(): Promise<any> {
  const target = window as YandexWindow
  if (target.ymaps) return new Promise(resolve => target.ymaps.ready(() => resolve(target.ymaps)))
  if (loader) return loader

  loader = new Promise((resolve, reject) => {
    const existing = document.getElementById('yandex-maps-api') as HTMLScriptElement | null
    const ready = () => {
      const ymaps = (window as YandexWindow).ymaps
      if (!ymaps) { reject(new Error('Yandex Maps API не инициализировался')); return }
      ymaps.ready(() => resolve(ymaps))
    }

    if (existing) {
      if ((window as YandexWindow).ymaps) ready()
      else {
        existing.addEventListener('load', ready, { once:true })
        existing.addEventListener('error', () => { existing.remove(); reject(new Error('Не удалось загрузить Yandex Maps API')) }, { once:true })
      }
      return
    }

    const apiKey = (import.meta.env.VITE_YANDEX_MAPS_API_KEY || '').trim()
    const script = document.createElement('script')
    script.id = 'yandex-maps-api'
    script.async = true
    script.src = `https://api-maps.yandex.ru/2.1/?lang=ru_RU${apiKey ? `&apikey=${encodeURIComponent(apiKey)}` : ''}`
    script.addEventListener('load', ready, { once:true })
    script.addEventListener('error', () => { script.remove(); reject(new Error('Не удалось загрузить Yandex Maps API')) }, { once:true })
    document.head.append(script)
  }).catch(error => {
    loader = null
    throw error
  })

  return loader
}
