import { describe,expect,it } from 'vitest'
import { localMediaUrl,resolvePhotoUrl } from './media'

describe('local housing media bridge',() => {
  it('maps archive local_path into the public media tree',() => {
    expect(localMediaUrl('/dataset/media/sibdom/3991056/01.jpg')).toBe('/media/sibdom/3991056/01.jpg')
    expect(localMediaUrl('media/Квартира 1/фото 1.jpg')).toBe('/media/%D0%9A%D0%B2%D0%B0%D1%80%D1%82%D0%B8%D1%80%D0%B0%201/%D1%84%D0%BE%D1%82%D0%BE%201.jpg')
  })

  it('always prefers a backend supplied URL',() => {
    expect(resolvePhotoUrl({
      id:'p1',
      url:'https://cdn.example.test/photo.jpg',
      order:0,
      is_cover:true,
      local_path:'media/local.jpg',
      publication_allowed:false
    })).toBe('https://cdn.example.test/photo.jpg')
  })
})
