// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScorePanel } from './ScorePanel'
import { demoApartments } from '../data/demo'
import { rememberRecommendation } from '../lib/recommendations'
import type { RecommendationResponse } from '../types'
beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
it('shows the personal score without diagnostic warnings from the current response', () => {
  const response: RecommendationResponse = { request_id:'req-detail',model_version:'demo-no-model',scoring_version:'demo-weighted-v1',ml_available:false,warnings:['Маршрут до работы не рассчитан'],items:[{ apartment_id:'a1',title:'Квартира',price:8900000,price_m2:140000,predicted_price_m2:null,score:8.7,scores:{schools:9,parks:8,transport:7,ecology:null,safety:null,commute:null,price:8},commute_minutes:null,reasons:['Школа рядом'],warnings:[],cover_image_url:null }] }
  rememberRecommendation(response)
  render(<ScorePanel apartment={demoApartments[0]}/>)
  expect(screen.getByText('8.7')).toBeTruthy()
  expect(screen.queryByText('Маршрут до работы не рассчитан')).toBeNull()
  expect(screen.getByText('Школа рядом')).toBeTruthy()
})
