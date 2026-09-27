// @vitest-environment jsdom
import { cleanup,fireEvent,render,screen } from '@testing-library/react'
import { afterEach,expect,it } from 'vitest'
import { RentVsBuyCalculator } from './RentVsBuyCalculator'

afterEach(cleanup)
const set=(name:string,value:string) => fireEvent.change(screen.getByRole('spinbutton',{name:new RegExp(name)}),{target:{value}})

it('updates the verdict when the selected horizon changes',() => {
  render(<RentVsBuyCalculator apartmentPrice={1_000_000} defaultDownPayment={1_000_000}/>)
  set('Аренда сейчас','10000')
  set('Срок сравнения','1')
  fireEvent.click(screen.getByRole('button',{name:'Настроить допущения'}))
  for (const label of ['Рост аренды','Рост цены жилья','Содержание жилья','Доходность свободных денег']) set(label,'0')
  set('Расходы при покупке','10')
  set('Расходы при продаже','10')
  expect(screen.getByText(/Выгоднее снимать: на/).textContent?.replace(/\s/g,'')).toBe('Выгоднееснимать:на80000₽')
  set('Срок сравнения','5')
  expect(screen.getByText(/Выгоднее купить: на/).textContent?.replace(/\s/g,'')).toBe('Выгоднеекупить:на400000₽')
})

it('accepts an actual mortgage rate and hides the verdict while fields are invalid',() => {
  render(<RentVsBuyCalculator apartmentPrice={6_000_000}/>)
  const result=document.querySelector('.rent-buy-difference')?.textContent
  set('Ваша ставка ипотеки','0')
  expect(document.querySelector('.rent-buy-difference')?.textContent).not.toBe(result)
  set('Ваша ставка ипотеки','')
  expect(screen.getByRole('alert').textContent).toContain('Заполните все поля')
  expect(document.querySelector('.rent-buy-result')).toBeNull()
  set('Ваша ставка ипотеки','16')
  expect(screen.queryByRole('alert')).toBeNull()
  expect(document.querySelector('.rent-buy-result')).not.toBeNull()
})

it('shows a tie without claiming either option wins',() => {
  render(<RentVsBuyCalculator apartmentPrice={1_000_000} defaultDownPayment={1_000_000}/>)
  set('Аренда сейчас','0')
  fireEvent.click(screen.getByRole('button',{name:'Настроить допущения'}))
  for (const label of ['Рост аренды','Рост цены жилья','Содержание жилья','Доходность свободных денег','Расходы при покупке','Расходы при продаже']) set(label,'0')
  expect(screen.getByText('Варианты равноценны по капиталу')).toBeTruthy()
})
