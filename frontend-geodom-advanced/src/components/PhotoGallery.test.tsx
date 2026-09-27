// @vitest-environment jsdom
import { fireEvent,render,screen } from '@testing-library/react'
import { expect,it } from 'vitest'
import { PhotoGallery } from './PhotoGallery'

it('opens a fullscreen gallery and supports keyboard navigation',() => {
  render(<PhotoGallery images={['/media/a.jpg','/media/b.jpg','/media/c.jpg']} title="Квартира"/>)

  fireEvent.click(screen.getByRole('button',{ name:'Открыть все фотографии' }))
  expect(screen.getByRole('dialog',{ name:'Фотографии: Квартира' })).toBeTruthy()
  expect(screen.getByAltText('Квартира — фото 1 из 3')).toBeTruthy()

  fireEvent.keyDown(window,{ key:'ArrowRight' })
  expect(screen.getByAltText('Квартира — фото 2 из 3')).toBeTruthy()

  fireEvent.keyDown(window,{ key:'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('deduplicates repeated media URLs',() => {
  render(<PhotoGallery images={['/media/a.jpg','/media/a.jpg','/media/b.jpg']} title="Квартира"/>)
  expect(screen.getByText('01 / 02')).toBeTruthy()
})
