import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Expand, X } from 'lucide-react'

export function PhotoGallery({ images,title }:{ images:string[];title:string }) {
  const normalized=useMemo(() => [...new Set(images.filter(Boolean))],[images])
  const [index,setIndex]=useState(0)
  const [open,setOpen]=useState(false)

  useEffect(() => {
    if (index >= normalized.length) setIndex(0)
  },[index,normalized.length])

  useEffect(() => {
    if (!normalized.length) return
    const next=(index+1)%normalized.length
    const image=new Image()
    image.src=normalized[next]
  },[index,normalized])

  useEffect(() => {
    if (!open) return
    const previousOverflow=document.body.style.overflow
    document.body.style.overflow='hidden'
    const onKeyDown=(event:KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
      if (event.key === 'ArrowLeft') setIndex(current => (current+normalized.length-1)%normalized.length)
      if (event.key === 'ArrowRight') setIndex(current => (current+1)%normalized.length)
      if (event.key === 'Home') setIndex(0)
      if (event.key === 'End') setIndex(Math.max(0,normalized.length-1))
    }
    window.addEventListener('keydown',onKeyDown)
    return () => {
      window.removeEventListener('keydown',onKeyDown)
      document.body.style.overflow=previousOverflow
    }
  },[open,normalized.length])

  if (!normalized.length) {
    return <div className="gallery gallery-empty"><div className="gallery-main"><div className="image-placeholder">GEODOM</div></div></div>
  }

  const previous=() => setIndex(current => (current+normalized.length-1)%normalized.length)
  const next=() => setIndex(current => (current+1)%normalized.length)
  const visibleThumbs=normalized.slice(Math.max(0,index-2),Math.max(0,index-2)+5)

  return <>
    <div className="gallery">
      <div className="gallery-main">
        <button type="button" className="gallery-expand" onClick={() => setOpen(true)} aria-label="Открыть все фотографии"><Expand size={17}/> Все фото</button>
        <img src={normalized[index]} alt={`${title} — фото ${index+1}`} fetchPriority={index === 0 ? 'high' : 'auto'}/>
        {normalized.length > 1 && <>
          <button type="button" className="gallery-arrow previous" aria-label="Предыдущее фото" onClick={previous}><ChevronLeft/></button>
          <button type="button" className="gallery-arrow next" aria-label="Следующее фото" onClick={next}><ChevronRight/></button>
        </>}
        <div className="gallery-counter">{String(index+1).padStart(2,'0')} / {String(normalized.length).padStart(2,'0')}</div>
      </div>

      {normalized.length > 1 && <div className="gallery-thumbs">
        {visibleThumbs.map(url => {
          const absoluteIndex=normalized.indexOf(url)
          return <button type="button" key={url} className={index === absoluteIndex ? 'active' : ''} onClick={() => setIndex(absoluteIndex)} aria-label={`Показать фото ${absoluteIndex+1}`}>
            <img src={url} alt="" loading="lazy"/>
            {absoluteIndex === index && <span>{absoluteIndex+1}</span>}
          </button>
        })}
        {normalized.length > visibleThumbs.length && <button type="button" className="gallery-more" onClick={() => setOpen(true)}><b>+{normalized.length-visibleThumbs.length}</b><span>все фото</span></button>}
      </div>}
    </div>

    {open && <div className="photo-lightbox" role="dialog" aria-modal="true" aria-label={`Фотографии: ${title}`} onClick={() => setOpen(false)}>
      <div className="photo-lightbox-inner" onClick={event => event.stopPropagation()}>
        <button type="button" className="photo-lightbox-close" onClick={() => setOpen(false)} aria-label="Закрыть"><X/></button>
        <img src={normalized[index]} alt={`${title} — фото ${index+1} из ${normalized.length}`}/>
        {normalized.length > 1 && <>
          <button type="button" className="photo-lightbox-arrow previous" onClick={previous} aria-label="Предыдущее фото"><ChevronLeft/></button>
          <button type="button" className="photo-lightbox-arrow next" onClick={next} aria-label="Следующее фото"><ChevronRight/></button>
        </>}
        <div className="photo-lightbox-counter">{index+1} / {normalized.length}</div>
        {normalized.length > 1 && <div className="photo-lightbox-strip">
          {normalized.map((url,itemIndex) => <button type="button" key={url} className={itemIndex === index ? 'active' : ''} onClick={() => setIndex(itemIndex)} aria-label={`Фото ${itemIndex+1}`}>
            <img src={url} alt="" loading="lazy"/>
          </button>)}
        </div>}
      </div>
    </div>}
  </>
}
