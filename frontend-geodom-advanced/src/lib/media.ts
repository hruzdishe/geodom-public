import { localHousingMedia } from '../data/localHousingMedia.generated'
import type { Apartment, ApartmentPhoto } from '../types'

function cleanPath(value:string) {
  return value.replace(/\\/g,'/').replace(/^\.\//,'').replace(/^\/+/, '')
}

function localMediaRelativePath(value:string) {
  const path=cleanPath(value)
  const marker='/media/'
  const index=path.lastIndexOf(marker)
  if (index >= 0) return path.slice(index+marker.length)
  if (path.startsWith('media/')) return path.slice('media/'.length)
  return path
}

function encodedPath(value:string) {
  return value.split('/').filter(Boolean).map(encodeURIComponent).join('/')
}

const base=(import.meta.env.VITE_LOCAL_MEDIA_BASE_URL || '/media').replace(/\/$/,'')
const live=!!import.meta.env.VITE_API_URL
const allowUnverifiedLocalMedia=!live && import.meta.env.DEV && import.meta.env.VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA !== 'false'

export function localMediaUrl(value:string|null|undefined) {
  if (!value) return null
  const relative=localMediaRelativePath(value)
  return relative ? `${base}/${encodedPath(relative)}` : null
}

export function resolvePhotoUrl(photo:Partial<ApartmentPhoto>) {
  if (live && photo.publication_allowed === false) return null
  const url=typeof photo.url === 'string' ? photo.url.trim() : ''
  if (url) return url
  if (live) return null
  if (photo.publication_allowed === false && !allowUnverifiedLocalMedia) return null
  return localMediaUrl(photo.local_path || photo.storage_key)
}

function allowed(photo:{ publication_allowed?:boolean }) {
  return photo.publication_allowed !== false || allowUnverifiedLocalMedia
}

export function localPhotosForApartmentId(id:string|number) {
  if (live) return []
  const photos=localHousingMedia[String(id)] || []
  return [...photos]
    .filter(allowed)
    .sort((a,b) => a.order-b.order)
    .map(photo => ({ ...photo,url:resolvePhotoUrl(photo) || '' }))
    .filter(photo => !!photo.url)
}

export function localCoverForApartmentId(id:string|number) {
  const photos=localPhotosForApartmentId(id)
  return photos.find(photo => photo.is_cover)?.url || photos[0]?.url || null
}

export function withLocalHousingMedia(apartment:Apartment):Apartment {
  if (live) return apartment
  if (apartment.photos.some(photo => resolvePhotoUrl(photo))) return apartment

  const candidates=[
    apartment.id,
    apartment.external_id,
    apartment.upstream_source && apartment.upstream_source_id
      ? `${apartment.upstream_source}:${apartment.upstream_source_id}`
      : undefined
  ].filter((value):value is string => !!value)

  for (const key of candidates) {
    const photos=localPhotosForApartmentId(key)
    if (!photos.length) continue
    return { ...apartment,photos }
  }

  if (apartment.cover_storage_key && allowUnverifiedLocalMedia) {
    const url=localMediaUrl(apartment.cover_storage_key)
    if (url) {
      return {
        ...apartment,
        photos:[{
          id:`local-cover:${apartment.id}`,
          url,
          order:0,
          is_cover:true,
          storage_key:apartment.cover_storage_key
        }]
      }
    }
  }

  return apartment
}
