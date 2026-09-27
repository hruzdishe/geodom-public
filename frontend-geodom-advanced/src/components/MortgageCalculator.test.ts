import { describe,expect,it } from 'vitest'
import { buildMortgageWizardOffers,calculateMortgage } from './MortgageCalculator'

describe('mortgage calculator',() => {
  it('calculates a standard annuity payment',() => {
    const result=calculateMortgage(10_000_000,2_000_000,12,20)
    expect(result.principal).toBe(8_000_000)
    expect(Math.round(result.monthlyPayment)).toBe(88087)
    expect(result.totalPayment).toBeGreaterThan(result.principal)
    expect(result.overpayment).toBeGreaterThan(0)
  })

  it('handles zero interest and clamps the down payment',() => {
    expect(calculateMortgage(6_000_000,1_000_000,0,10).monthlyPayment).toBeCloseTo(41666.666,2)
    expect(calculateMortgage(6_000_000,9_000_000,20,20)).toEqual({
      principal:0,monthlyPayment:0,totalPayment:0,overpayment:0
    })
  })

  it('keeps near-zero positive rates numerically stable',() => {
    const result=calculateMortgage(1_200_000,0,1e-12,1)
    expect(result.monthlyPayment).toBeCloseTo(100_000,5)
  })

  it('sorts secondary offers by usable monthly payment',() => {
    const offers=buildMortgageWizardOffers({
      scenario:'secondary',
      price:8_000_000,
      downPayment:2_000_000,
      years:20
    })
    const eligible=offers.filter(item => item.eligible && item.result)
    expect(eligible.length).toBeGreaterThan(1)
    expect(eligible[0].result!.monthlyPayment).toBeLessThanOrEqual(eligible[1].result!.monthlyPayment)
    expect(offers).toHaveLength(19)
  })

  it('uses the family program rate across candidate banks and flags it as program-level',() => {
    const offers=buildMortgageWizardOffers({
      scenario:'family',
      price:7_000_000,
      downPayment:1_500_000,
      years:20,
      childrenCount:1,
      youngestChildAge:3
    })
    expect(offers).toHaveLength(19)
    expect(offers.every(item => item.programRate)).toBe(true)
    expect(new Set(offers.map(item => item.rate)).size).toBe(1)
  })

  it('marks new-build bank rates as estimated until a dedicated feed exists',() => {
    const offers=buildMortgageWizardOffers({
      scenario:'newbuild',
      price:8_000_000,
      downPayment:2_000_000,
      years:20
    })
    expect(offers.every(item => item.estimated)).toBe(true)
  })
})
