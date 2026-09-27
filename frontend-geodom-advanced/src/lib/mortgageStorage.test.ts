// @vitest-environment jsdom
import { beforeEach,describe,expect,it } from 'vitest'
import {
  clearMortgageWizardDraft,
  deleteSavedMortgageCalculation,
  loadMortgageWizardDraft,
  loadSavedMortgageCalculations,
  saveMortgageCalculation,
  saveMortgageWizardDraft
} from './mortgageStorage'

beforeEach(() => localStorage.clear())

describe('mortgage storage',() => {
  it('restores a draft only for the same apartment price',() => {
    saveMortgageWizardDraft({
      sourcePrice:8_000_000,step:3,scenario:'family',bankId:'sber',propertyPrice:8_200_000,downPayment:2_000_000,
      years:20,monthlyIncome:180_000,existingPayments:12_000,employment:'employee',childrenCount:2,youngestChildAge:3,itAccredited:false,updatedAt:new Date().toISOString()
    })
    expect(loadMortgageWizardDraft(8_000_000)?.step).toBe(3)
    expect(loadMortgageWizardDraft(9_000_000)).toBeNull()
    clearMortgageWizardDraft()
    expect(loadMortgageWizardDraft(8_000_000)).toBeNull()
  })

  it('stores and deletes saved calculations',() => {
    saveMortgageCalculation({
      id:'c1',createdAt:new Date().toISOString(),apartmentPrice:8_000_000,downPayment:2_000_000,years:20,
      scenario:'secondary',bankId:'sber',bank:'СберБанк',rate:14.5,monthlyPayment:76_000,totalPayment:18_000_000,overpayment:12_000_000
    })
    expect(loadSavedMortgageCalculations()).toHaveLength(1)
    deleteSavedMortgageCalculation('c1')
    expect(loadSavedMortgageCalculations()).toHaveLength(0)
  })
})
