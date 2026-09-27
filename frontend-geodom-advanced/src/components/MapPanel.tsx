import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { ChevronDown, Layers3 } from 'lucide-react'
import type { Apartment } from '../types'
import { price } from '../lib/catalog'
import { validCoordinate, type GeoObject } from '../lib/dataSanitizers'
import { loadYandexMaps } from '../lib/yandexMaps'
import { createSpatialIndex, type SpatialBounds } from '../lib/spatialIndex'

type WorkLocation = { lat:number; lon:number } | null
type PoiLayer = 'education' | 'parks' | 'healthcare' | 'transport' | 'daily' | 'parking'

const CITY_OVERVIEW_MAX_ZOOM = 8
const DISTRICT_CARD_MAX_ZOOM = 9
const APARTMENT_CLUSTER_MIN_ZOOM = 11
const APARTMENT_PRICE_MIN_ZOOM = 13
const POI_MIN_ZOOM = 16
const MAX_PRICE_PINS = 320
const MAX_COMPACT_PRICE_PINS = 140
const COMPACT_PRICE_PIN_MAX_ZOOM = 14
const MAX_POI_MARKS = 1200

const layerMeta: Array<{ key:PoiLayer; label:string; preset:string }> = [
  { key:'education',label:'Школы и детсады',preset:'islands#blueIcon' },
  { key:'parks',label:'Парки и зелень',preset:'islands#greenIcon' },
  { key:'healthcare',label:'Медицина',preset:'islands#redIcon' },
  { key:'parking',label:'Парковки',preset:'islands#grayIcon' },
  { key:'transport',label:'Транспорт',preset:'islands#violetIcon' },
  { key:'daily',label:'Магазины и сервисы',preset:'islands#orangeIcon' }
]

function escapeHtml(value:string) {
  return value.replace(/[&<>"']/g,char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char] || char))
}

function safeHttpUrl(value:string|null) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function score10(value:number|null) {
  if (value === null || !Number.isFinite(value)) return null
  return value > 10 ? value/10 : value
}

function boundsFromYandex(value:unknown):SpatialBounds|null {
  if (!Array.isArray(value) || value.length < 2) return null
  const first=value[0]
  const second=value[1]
  if (!Array.isArray(first) || !Array.isArray(second)) return null
  const lat1=Number(first[0]); const lon1=Number(first[1])
  const lat2=Number(second[0]); const lon2=Number(second[1])
  if (![lat1,lon1,lat2,lon2].every(Number.isFinite)) return null
  return {
    minLat:Math.min(lat1,lat2),
    maxLat:Math.max(lat1,lat2),
    minLon:Math.min(lon1,lon2),
    maxLon:Math.max(lon1,lon2)
  }
}

export function classifyGeoObject(item:GeoObject):PoiLayer|null {
  const value=`${item.category} ${item.subcategory || ''}`.toLowerCase()
  if (/(school|kindergarten|college|university|education|школ|сад|образован)/.test(value)) return 'education'
  if (/(parking|парков|стоянк)/.test(value)) return 'parking'
  if (/(park|garden|green|forest|recreation|парк|сквер|зел)/.test(value)) return 'parks'
  if (/(health|hospital|clinic|pharmacy|doctor|мед|больниц|поликлин|аптек)/.test(value)) return 'healthcare'
  if (/(transport|bus|tram|rail|station|stop|metro|транспорт|останов|вокзал)/.test(value)) return 'transport'
  if (/(shop|supermarket|market|cafe|restaurant|sport|fitness|amenity|магаз|кафе|ресторан|спорт)/.test(value)) return 'daily'
  return null
}

function removeOverlay(instance:any,overlayRef:MutableRefObject<any>) {
  if (!overlayRef.current) return
  try { instance.geoObjects.remove(overlayRef.current) } catch {}
  overlayRef.current=null
}

export function MapPanel({
  items,
  geoObjects,
  selectedDistrict,
  onDistrict,
  workLocation,
  workPicking,
  onWorkLocation,
  activeApartmentIds,
  scoreByApartment
}:{
  items:Apartment[]
  geoObjects:GeoObject[]
  selectedDistrict:string
  onDistrict:(district:string)=>void
  workLocation:WorkLocation
  workPicking:boolean
  onWorkLocation:(location:{ lat:number;lon:number })=>void
  activeApartmentIds?:Set<string>
  scoreByApartment?:Map<string,number|null>
}) {
  const element=useRef<HTMLDivElement>(null)
  const map=useRef<any>(null)
  const ymapsRef=useRef<any>(null)
  const districtHandler=useRef(onDistrict)
  const workHandler=useRef(onWorkLocation)
  const pickingRef=useRef(workPicking)
  const resizeObserver=useRef<ResizeObserver|null>(null)
  const viewportTimer=useRef<number|null>(null)
  const fittedSignature=useRef('')
  const apartmentOverlay=useRef<any>(null)
  const districtOverlay=useRef<any>(null)
  const poiOverlay=useRef<any>(null)
  const workOverlay=useRef<any>(null)

  const [ready,setReady]=useState(false)
  const [zoom,setZoom]=useState(11)
  const [viewport,setViewport]=useState<SpatialBounds|null>(null)
  const [loadError,setLoadError]=useState('')
  const [layersOpen,setLayersOpen]=useState(() => typeof window === 'undefined' ? true : !window.matchMedia('(max-width:520px)').matches)
  const [layers,setLayers]=useState<Record<PoiLayer,boolean>>({
    education:true,
    parks:true,
    healthcare:true,
    transport:true,
    daily:false,
    parking:true
  })

  districtHandler.current=onDistrict
  workHandler.current=onWorkLocation
  pickingRef.current=workPicking

  const layerCounts=useMemo(() => {
    const counts:Record<PoiLayer,number>={ education:0,parks:0,healthcare:0,transport:0,daily:0,parking:0 }
    for (const item of geoObjects) {
      const layer=classifyGeoObject(item)
      if (layer) counts[layer]+=1
    }
    return counts
  },[geoObjects])

  const validApartments=useMemo(
    () => items.filter(item => item.status === 'published' && validCoordinate(item.latitude,item.longitude)),
    [items]
  )
  const validApartmentCount=validApartments.length

  const apartmentIndex=useMemo(
    () => createSpatialIndex(validApartments,item => validCoordinate(item.latitude,item.longitude),.015),
    [validApartments]
  )
  const poiIndex=useMemo(
    () => createSpatialIndex(geoObjects,item => ({ lat:item.lat,lon:item.lon }),.015),
    [geoObjects]
  )

  const apartmentMode:'hidden'|'cluster'|'prices'=zoom <= CITY_OVERVIEW_MAX_ZOOM
    ? 'hidden'
    : zoom < APARTMENT_CLUSTER_MIN_ZOOM
      ? 'hidden'
      : zoom < APARTMENT_PRICE_MIN_ZOOM
        ? 'cluster'
        : 'prices'

  const visibleApartments=useMemo(
    () => apartmentMode === 'hidden' ? [] : apartmentIndex.query(viewport,{ padding:.18 }),
    [apartmentIndex,viewport,apartmentMode]
  )
  const compactPricePins=apartmentMode === 'prices' && zoom <= COMPACT_PRICE_PIN_MAX_ZOOM
  const pricePinBudget=compactPricePins ? MAX_COMPACT_PRICE_PINS : MAX_PRICE_PINS
  const useApartmentClusters=apartmentMode === 'cluster' || (apartmentMode === 'prices' && visibleApartments.length > pricePinBudget)

  const eligiblePoi=useMemo(
    () => zoom >= POI_MIN_ZOOM ? poiIndex.query(viewport,{ padding:.18 }) : [],
    [poiIndex,zoom,viewport]
  )
  const visiblePoi=useMemo(() => {
    const enabled=layerMeta.filter(layer => layers[layer.key])
    const limit=Math.floor(MAX_POI_MARKS/Math.max(1,enabled.length))
    return enabled.flatMap(layer => eligiblePoi.filter(item => classifyGeoObject(item) === layer.key).slice(0,limit))
  },[eligiblePoi,layers])

  const districtGroups=useMemo(() => {
    const groups=new Map<string,Apartment[]>()
    for (const item of validApartments) groups.set(item.district.name,[...(groups.get(item.district.name) || []),item])
    return groups
  },[validApartments])

  useEffect(() => {
    let cancelled=false
    if (!element.current || map.current) return

    loadYandexMaps().then(ymaps => {
      if (cancelled || !element.current) return
      const instance=new ymaps.Map(element.current,{
        center:[56.014,92.87],
        zoom:11,
        controls:['zoomControl','fullscreenControl']
      },{
        minZoom:3,
        maxZoom:19,
        suppressMapOpenBlock:true
      })

      instance.behaviors.enable(['drag','scrollZoom','dblClickZoom','multiTouch'])
      const syncViewport=() => {
        if (viewportTimer.current !== null) window.clearTimeout(viewportTimer.current)
        viewportTimer.current=window.setTimeout(() => {
          setZoom(instance.getZoom())
          setViewport(boundsFromYandex(instance.getBounds()))
        },90)
      }
      instance.events.add('boundschange',syncViewport)
      syncViewport()
      instance.events.add('click',(event:any) => {
        if (!pickingRef.current) return
        const coords=event.get('coords')
        const point=validCoordinate(coords?.[0],coords?.[1])
        if (point) workHandler.current(point)
      })

      ymapsRef.current=ymaps
      map.current=instance
      resizeObserver.current=new ResizeObserver(() => instance.container.fitToViewport())
      resizeObserver.current.observe(element.current)
      setReady(true)
    }).catch(error => {
      if (!cancelled) setLoadError(error instanceof Error ? error.message : 'Не удалось загрузить карту')
    })

    return () => {
      cancelled=true
      resizeObserver.current?.disconnect()
      resizeObserver.current=null
      if (viewportTimer.current !== null) window.clearTimeout(viewportTimer.current)
      viewportTimer.current=null
      map.current?.destroy()
      map.current=null
      ymapsRef.current=null
    }
  },[])

  useEffect(() => {
    const instance=map.current
    if (!ready || !instance || workPicking || !validApartments.length) return
    const signature=validApartments.map(item => `${item.id}:${item.latitude}:${item.longitude}`).sort().join('|')
    if (!signature || signature === fittedSignature.current) return

    const points=validApartments
      .map(item => validCoordinate(item.latitude,item.longitude))
      .filter((point):point is { lat:number;lon:number } => point !== null)

    if (points.length > 1) {
      const latitudes=points.map(point => point.lat)
      const longitudes=points.map(point => point.lon)
      instance.setBounds([
        [Math.min(...latitudes),Math.min(...longitudes)],
        [Math.max(...latitudes),Math.max(...longitudes)]
      ],{ checkZoomRange:true,zoomMargin:[48,48] })
    } else if (points.length === 1) {
      instance.setCenter([points[0].lat,points[0].lon],13)
    }
    fittedSignature.current=signature
  },[ready,validApartments,workPicking])

  useEffect(() => {
    const instance=map.current
    const ymaps=ymapsRef.current
    if (!ready || !instance || !ymaps) return

    removeOverlay(instance,apartmentOverlay)
    if (workPicking || apartmentMode === 'hidden' || !visibleApartments.length) return

    if (useApartmentClusters) {
      const features=visibleApartments.flatMap((item,index) => {
        const point=validCoordinate(item.latitude,item.longitude)
        if (!point) return []
        const activeByFilter=!activeApartmentIds || activeApartmentIds.has(String(item.id))
        const activeByDistrict=!selectedDistrict || selectedDistrict === item.district.name
        const active=activeByFilter && activeByDistrict
        const personalScore=scoreByApartment?.get(String(item.id))
        const displayedScore=typeof personalScore === 'number' && Number.isFinite(personalScore)
          ? personalScore
          : score10(item.recommendation.score)

        return [{
          type:'Feature',
          id:`${item.id}-${index}`,
          geometry:{ type:'Point',coordinates:[point.lat,point.lon] },
          properties:{
            balloonContentHeader:escapeHtml(item.title),
            balloonContentBody:`<strong>${escapeHtml(price(item.price))}</strong>${displayedScore === null ? '' : `<br><b>Персональная оценка: ${displayedScore.toFixed(1)} / 10</b>`}<br><span>${escapeHtml(item.address)}</span><br><a href="/apartments/${encodeURIComponent(item.id)}">Открыть квартиру →</a>`
          },
          options:{ preset:active ? 'islands#blueCircleIcon' : 'islands#grayCircleIcon' }
        }]
      })

      if (!features.length) return
      const objectManager=new ymaps.ObjectManager({
        clusterize:true,
        gridSize:72,
        clusterDisableClickZoom:false,
        geoObjectOpenBalloonOnClick:true
      })
      objectManager.clusters.options.set('preset','islands#blueClusterIcons')
      objectManager.add({ type:'FeatureCollection',features })
      apartmentOverlay.current=objectManager
      instance.geoObjects.add(objectManager)
      return
    }

    const collection=new ymaps.GeoObjectCollection()
    for (const item of visibleApartments) {
      const point=validCoordinate(item.latitude,item.longitude)
      if (!point) continue
      const activeByFilter=!activeApartmentIds || activeApartmentIds.has(String(item.id))
      const activeByDistrict=!selectedDistrict || selectedDistrict === item.district.name
      const active=activeByFilter && activeByDistrict
      const amount=new Intl.NumberFormat('ru-RU',{ maximumFractionDigits:1 }).format(item.price/1000000)
      const personalScore=scoreByApartment?.get(String(item.id))
      const displayedScore=typeof personalScore === 'number' && Number.isFinite(personalScore)
        ? personalScore
        : score10(item.recommendation.score)
      const layout=ymaps.templateLayoutFactory.createClass(
        `<div class="yandex-price-pin ${compactPricePins ? 'compact' : ''} ${active ? '' : 'muted'}"><span class="price-short">${amount}м</span><span class="price-full">${amount} млн ₽</span></div>`
      )
      const placemark=new ymaps.Placemark(
        [point.lat,point.lon],
        {
          balloonContentHeader:escapeHtml(item.title),
          balloonContentBody:`<strong>${escapeHtml(price(item.price))}</strong>${displayedScore === null ? '' : `<br><b>Персональная оценка: ${displayedScore.toFixed(1)} / 10</b>`}<br><span>${escapeHtml(item.address)}</span><br><a href="/apartments/${encodeURIComponent(item.id)}">Открыть квартиру →</a>`
        },
        {
          iconLayout:layout,
          iconShape:{ type:'Rectangle',coordinates:[[-60,-38],[60,5]] },
          interactiveZIndex:true,
          zIndex:900,
          zIndexHover:12000,
          zIndexActive:13000
        }
      )
      placemark.events.add('mouseenter',() => placemark.options.set({
        zIndex:12000,
        zIndexHover:12000,
        zIndexActive:13000
      }))
      placemark.events.add('mouseleave',() => placemark.options.set({
        zIndex:900,
        zIndexHover:12000,
        zIndexActive:13000
      }))
      placemark.events.add('balloonopen',() => placemark.options.set('zIndex',13000))
      placemark.events.add('balloonclose',() => placemark.options.set('zIndex',900))
      collection.add(placemark)
    }
    apartmentOverlay.current=collection
    instance.geoObjects.add(collection)
  },[ready,apartmentMode,visibleApartments,useApartmentClusters,compactPricePins,activeApartmentIds,selectedDistrict,scoreByApartment,workPicking])

  useEffect(() => {
    const instance=map.current
    const ymaps=ymapsRef.current
    if (!ready || !instance || !ymaps) return

    removeOverlay(instance,districtOverlay)
    if (workPicking) return
    const collection=new ymaps.GeoObjectCollection()

    if (zoom <= CITY_OVERVIEW_MAX_ZOOM && validApartments.length) {
      const points=validApartments
        .map(item => validCoordinate(item.latitude,item.longitude))
        .filter((point):point is { lat:number;lon:number } => point !== null)
      const lat=points.reduce((sum,point) => sum+point.lat,0)/points.length
      const lon=points.reduce((sum,point) => sum+point.lon,0)/points.length
      const layout=ymaps.templateLayoutFactory.createClass(
        `<div class="yandex-city-summary"><strong>Красноярск</strong><span>${validApartments.length} квартир</span><small>Приблизьте карту</small></div>`
      )
      const cityPlacemark=new ymaps.Placemark([lat,lon],{},{
        iconLayout:layout,
        iconShape:{ type:'Rectangle',coordinates:[[-70,-70],[70,5]] },
        interactiveZIndex:false,
        zIndex:1100,
        zIndexHover:1100
      })
      cityPlacemark.events.add('click',() => instance.setCenter([lat,lon],10,{ checkZoomRange:true,duration:260 }))
      collection.add(cityPlacemark)
    } else if (zoom > CITY_OVERVIEW_MAX_ZOOM) {
      const compactDistricts=zoom > DISTRICT_CARD_MAX_ZOOM
      for (const [district,houses] of districtGroups) {
        const points=houses
          .map(home => validCoordinate(home.latitude,home.longitude))
          .filter((point):point is { lat:number;lon:number } => point !== null)
        if (!points.length) continue

        const lat=points.reduce((sum,point) => sum+point.lat,0)/points.length
        const lon=points.reduce((sum,point) => sum+point.lon,0)/points.length
        const scores=houses.map(home => {
          const personal=scoreByApartment?.get(String(home.id))
          return typeof personal === 'number' && Number.isFinite(personal) ? personal : score10(home.recommendation.score)
        }).filter((value):value is number => value !== null)
        const average=scores.length ? scores.reduce((sum,value) => sum+value,0)/scores.length : null
        const active=selectedDistrict === district
        const html=compactDistricts
          ? `<div class="yandex-district-dot ${active ? 'active' : ''}" title="${escapeHtml(district)}"></div>`
          : `<div class="yandex-district-pin ${active ? 'active' : ''}"><span>${escapeHtml(district)}</span><div>${average === null ? '<b>—</b>' : `<b>${average.toFixed(1)}</b>`}<em>/10</em></div><small>${houses.length} ${houses.length === 1 ? 'квартира' : houses.length < 5 ? 'квартиры' : 'квартир'}</small></div>`
        const layout=ymaps.templateLayoutFactory.createClass(html)
        const placemark=new ymaps.Placemark([lat,lon],{ hintContent:escapeHtml(district) },{
          iconLayout:layout,
          iconShape:compactDistricts
            ? { type:'Circle',coordinates:[0,0],radius:9 }
            : { type:'Rectangle',coordinates:[[-48,-48],[48,0]] },
          interactiveZIndex:true,
          zIndex:compactDistricts ? 620 : 1050,
          zIndexHover:compactDistricts ? 1800 : 3200,
          zIndexActive:compactDistricts ? 1900 : 3300
        })
        placemark.events.add('click',() => {
          districtHandler.current(district)
          if (!compactDistricts) instance.setCenter([lat,lon],13,{ checkZoomRange:true,duration:260 })
        })
        collection.add(placemark)
      }
    }

    districtOverlay.current=collection
    instance.geoObjects.add(collection)
  },[ready,zoom,validApartments,districtGroups,selectedDistrict,scoreByApartment,workPicking])

  useEffect(() => {
    const instance=map.current
    const ymaps=ymapsRef.current
    if (!ready || !instance || !ymaps) return

    removeOverlay(instance,poiOverlay)
    if (workPicking || !visiblePoi.length) return

    const marks:any[]=[]
    for (const item of visiblePoi) {
      const layer=classifyGeoObject(item)
      if (!layer || !layers[layer]) continue
      const meta=layerMeta.find(candidate => candidate.key === layer)
      if (!meta) continue
      const sourceUrl=safeHttpUrl(item.sourceUrl)
      const body=[
        item.address ? `<span>${escapeHtml(item.address)}</span>` : '',
        item.source ? `<small>Источник: ${escapeHtml(item.source)}</small>` : '',


        sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Открыть источник →</a>` : ''
      ].filter(Boolean).join('<br>')

      marks.push(new ymaps.Placemark([item.lat,item.lon],{
        iconContent:layer === 'parking' ? 'P' : undefined,
        hintContent:escapeHtml(item.name),
        balloonContentHeader:escapeHtml(item.name),
        balloonContentBody:body || 'Данные об объекте инфраструктуры'
      },{
        preset:meta.preset,
        zIndex:220
      }))
    }

    if (!marks.length) return
    const clusterer=new ymaps.Clusterer({
      groupByCoordinates:false,
      clusterDisableClickZoom:false,
      clusterHideIconOnBalloonOpen:false,
      geoObjectHideIconOnBalloonOpen:false,
      gridSize:64
    })
    clusterer.add(marks)
    poiOverlay.current=clusterer
    instance.geoObjects.add(clusterer)
  },[ready,visiblePoi,layers,workPicking])

  useEffect(() => {
    const instance=map.current
    const ymaps=ymapsRef.current
    if (!ready || !instance || !ymaps) return

    removeOverlay(instance,workOverlay)
    const point=workLocation ? validCoordinate(workLocation.lat,workLocation.lon) : null
    if (!point) return

    const placemark=new ymaps.Placemark(
      [point.lat,point.lon],
      { iconCaption:'Работа',hintContent:'Место работы',balloonContent:'Выбранное место работы' },
      { preset:'islands#redIcon',draggable:true,zIndex:1500 }
    )
    placemark.events.add('dragend',() => {
      const coords=placemark.geometry.getCoordinates()
      const next=validCoordinate(coords?.[0],coords?.[1])
      if (next) workHandler.current(next)
    })
    workOverlay.current=placemark
    instance.geoObjects.add(placemark)
  },[ready,workLocation])

  return <div className={`map-wrapper yandex-map-wrapper ${workPicking ? 'work-picking' : ''}`}>
    <div ref={element} className="map-canvas" aria-label="Яндекс Карта квартир Красноярска"/>
    {loadError && <div className="map-load-error"><b>Яндекс Карта недоступна</b><span>{loadError}</span><small>Попробуйте обновить страницу.</small></div>}
    {workPicking && <div className="work-pick-hint">Нажмите на карте в точке, где находится работа</div>}

    <div className={`map-layer-panel ${layersOpen ? 'open' : 'collapsed'}`} aria-label="Слои инфраструктуры">
      <button type="button" className="map-layer-toggle" onClick={() => setLayersOpen(value => !value)} aria-expanded={layersOpen}>
        <Layers3 size={15}/><b>Слои на карте</b><small>{validApartmentCount} кв. · {geoObjects.length} объектов</small><ChevronDown size={14}/>
      </button>
      {layersOpen && <>
        <div className="map-lod-status">{
          zoom <= CITY_OVERVIEW_MAX_ZOOM
            ? 'Приблизьте карту, чтобы увидеть квартиры и объекты'
            : zoom < APARTMENT_CLUSTER_MIN_ZOOM
              ? 'Районы · квартиры появятся при приближении'
              : useApartmentClusters
                ? `Кластеры квартир · ${visibleApartments.length} в текущей области`
                : compactPricePins
                  ? `Компактные цены · ${visibleApartments.length} в текущей области`
                  : `Цены квартир · ${visibleApartments.length} в текущей области`
        }</div>
        {layerMeta.map(layer => <button
          type="button"
          key={layer.key}
          className={layers[layer.key] ? 'active' : ''}
          onClick={() => setLayers(current => ({ ...current,[layer.key]:!current[layer.key] }))}
          aria-pressed={layers[layer.key]}
        >
          <i className={`poi-dot ${layer.key}`}/>
          <span>{layer.label}</span>
          <small>{layerCounts[layer.key]}</small>
        </button>)}
        {items.length !== validApartmentCount && <div className="map-data-warning">{items.length-validApartmentCount} квартир без валидных координат скрыто</div>}
        {eligiblePoi.length > MAX_POI_MARKS && <div className="map-data-warning">Показано {MAX_POI_MARKS} из {eligiblePoi.length} объектов текущего окна</div>}
      </>}
    </div>

    <div className="map-legend">
      <span><i className="legend-dot blue"/> Квартиры</span>
      <span><i className="legend-dot green"/> Районы</span>
      <span><i className="legend-dot red"/> Работа</span>
    </div>
  </div>
}
