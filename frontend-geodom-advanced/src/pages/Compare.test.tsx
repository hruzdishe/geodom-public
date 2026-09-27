// @vitest-environment jsdom
import { beforeEach,expect,it } from 'vitest'
import { render,screen,waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Compare } from './Compare'
import { useGeoDomStore } from '../store/useGeoDomStore'
import { rememberRecommendation } from '../lib/recommendations'
import type { RecommendationResponse } from '../types'

const response:RecommendationResponse={
  request_id:'compare-test',
  model_version:'demo',
  scoring_version:'demo',
  ml_available:false,
  warnings:[],
  items:[
    { apartment_id:'a1',title:'Светлая квартира у набережной',price:8900000,price_m2:142628,predicted_price_m2:null,score:8.9,scores:{schools:9,parks:8,transport:7,ecology:null,safety:null,commute:null,price:8},commute_minutes:null,reasons:['Школы рядом'],warnings:[],cover_image_url:null },
    { apartment_id:'a2',title:'Квартира с видом на город',price:6900000,price_m2:125912,predicted_price_m2:null,score:8.4,scores:{schools:8,parks:7,transport:9,ecology:null,safety:null,commute:null,price:9},commute_minutes:null,reasons:['Транспорт рядом'],warnings:[],cover_image_url:null }
  ]
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  useGeoDomStore.setState({ comparedIds:['a1','a2'] })
  rememberRecommendation(response)
})

it('renders comparison as a dedicated page instead of a floating tray',async () => {
  render(<MemoryRouter><Compare/></MemoryRouter>)
  expect(screen.getByRole('heading',{name:'Сравнение квартир'})).toBeTruthy()
  await waitFor(() => expect(screen.getByText('Светлая квартира у набережной')).toBeTruthy())
  await waitFor(() => expect(screen.queryByText('Загружаем карточки…')).toBeNull())
  expect(screen.getByText('Школы до 1 км')).toBeTruthy()
  expect(screen.getByText('Цена за м²')).toBeTruthy()
  expect(screen.queryByRole('region',{name:'Сравнение квартир'})).toBeNull()
})
