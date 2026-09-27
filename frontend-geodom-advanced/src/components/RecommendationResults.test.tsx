// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RecommendationResults } from './RecommendationResults'
import { getSavedIds, readDemoEvents } from '../lib/recommendations'
import { useGeoDomStore } from '../store/useGeoDomStore'
import type { RecommendationResponse } from '../types'
const result: RecommendationResponse = {
  request_id:'req-ui-test', model_version:'demo-no-model', scoring_version:'demo-weighted-v1', ml_available:false,
  warnings:['Нет данных об экологии'],
  items:[{ apartment_id:'a1', title:'Светлая квартира', price:8900000, price_m2:140000, predicted_price_m2:null, score:8.7,
    scores:{schools:9,parks:8,transport:7,ecology:null,safety:null,commute:null,price:8}, commute_minutes:null,
    reasons:['Школа рядом','Парк рядом'], warnings:[],cover_image_url:null }]
}
beforeEach(() => { localStorage.clear(); useGeoDomStore.setState({ savedIds:[],comparedIds:[] }) })
it('hides diagnostic warnings and records an impression, save and compare with request context', async () => {
  render(<MemoryRouter><RecommendationResults response={result} loading={false} error="" onRetry={() => {}}/></MemoryRouter>)
  expect(screen.queryByText('Нет данных об экологии')).toBeNull()
  expect(screen.getByText('8.7')).toBeTruthy()
  await waitFor(() => expect(readDemoEvents().some(e => e.event === 'impression' && e.request_id === 'req-ui-test')).toBe(true))
  fireEvent.click(screen.getByRole('button',{name:'Сохранить квартиру'}))
  fireEvent.click(screen.getByRole('button',{name:'Добавить к сравнению'}))
  expect(getSavedIds()).toEqual(['a1'])
  expect(screen.getByRole('link',{name:/Открыть сравнение/})).toBeTruthy()
  await waitFor(() => expect(readDemoEvents().map(e => e.event)).toEqual(['impression','save','compare']))
})
