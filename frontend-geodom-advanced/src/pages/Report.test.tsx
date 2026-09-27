// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Report } from './Report'
import { defaultPreferences } from '../lib/preferences'
import { rememberRecommendation } from '../lib/recommendations'
import { useGeoDomStore } from '../store/useGeoDomStore'
import type { RecommendationResponse } from '../types'

const response:RecommendationResponse = {
  request_id:'req-report-123456',
  model_version:'demo-no-model',
  scoring_version:'demo-weighted-v1',
  ml_available:false,
  warnings:['Нет маршрутных данных'],
  items:[{
    apartment_id:'a1',
    title:'Квартира для отчёта',
    price:7500000,
    price_m2:150000,
    predicted_price_m2:null,
    score:8.4,
    scores:{ schools:9,parks:8,transport:7,ecology:null,safety:null,commute:null,price:8 },
    commute_minutes:null,
    reasons:['Школа рядом','Парк рядом'],
    warnings:[],
    cover_image_url:null
  }]
}

beforeEach(() => {
  localStorage.clear()
  useGeoDomStore.setState({ preferences:{ ...defaultPreferences,budget_max:9000000 } })
})

it('renders the last successful recommendation as a printable decision report', () => {
  rememberRecommendation(response)
  render(<MemoryRouter><Report/></MemoryRouter>)

  expect(screen.getByText('Короткий список для решения')).toBeTruthy()
  expect(screen.getByText('Квартира для отчёта')).toBeTruthy()
  expect(screen.queryByText('Нет маршрутных данных')).toBeNull()
  expect(screen.getByText('8.4')).toBeTruthy()
})
