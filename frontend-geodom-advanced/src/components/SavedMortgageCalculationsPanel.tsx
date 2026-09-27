import { useState } from 'react'
import { Calculator, Trash2 } from 'lucide-react'
import { price } from '../lib/catalog'
import { deleteSavedMortgageCalculation,loadSavedMortgageCalculations,type SavedMortgageCalculation } from '../lib/mortgageStorage'

function scenarioLabel(value:SavedMortgageCalculation['scenario']) {
  if (value === 'newbuild') return 'Новостройка'
  if (value === 'family') return 'Семейная ипотека'
  if (value === 'it') return 'IT-ипотека'
  return 'Вторичка'
}

export function SavedMortgageCalculationsPanel() {
  const [items,setItems]=useState(loadSavedMortgageCalculations)

  function remove(id:string) {
    setItems(deleteSavedMortgageCalculation(id))
  }

  return <section className="saved-mortgages-panel">
    <div className="saved-mortgages-head">
      <span><Calculator size={19}/></span>
      <div><small>ИПОТЕКА</small><h2>Сохранённые расчёты</h2><p>Последние сценарии сохраняются в этом браузере и не отправляются в банк.</p></div>
      <b>{items.length}</b>
    </div>

    {items.length ? <div className="saved-mortgage-list">{items.map(item => <article key={item.id}>
      <div className="saved-mortgage-main">
        <span>{scenarioLabel(item.scenario)}</span>
        <h3>{item.bank}</h3>
        <p>{price(Math.round(item.apartmentPrice))} · взнос {price(Math.round(item.downPayment))} · {item.years} лет</p>
      </div>
      <div className="saved-mortgage-payment">
        <span>Платёж</span>
        <b>{price(Math.round(item.monthlyPayment))}/мес</b>
        <small>{item.rate === null ? 'ставка уточнялась' : item.rate+'% годовых'} · {new Date(item.createdAt).toLocaleDateString('ru-RU')}</small>
      </div>
      <button type="button" aria-label={`Удалить расчёт ${item.bank}`} onClick={() => remove(item.id)}><Trash2 size={15}/></button>
    </article>)}</div> : <div className="saved-mortgage-empty">На странице квартиры откройте ипотечный калькулятор и нажмите «Сохранить расчёт» на последнем шаге.</div>}
  </section>
}
