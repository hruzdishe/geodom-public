export type MortgageScenario='newbuild'|'secondary'|'family'|'it'
export type MortgageEmployment='employee'|'self'|'business'

export type MortgageWizardDraft={
  sourcePrice:number
  step:1|2|3|4
  scenario:MortgageScenario
  bankId:string
  propertyPrice:number
  downPayment:number
  years:number
  monthlyIncome:number
  existingPayments:number
  employment:MortgageEmployment
  childrenCount:number
  youngestChildAge:number|null
  itAccredited:boolean
  updatedAt:string
}

export type SavedMortgageCalculation={
  id:string
  createdAt:string
  apartmentPrice:number
  downPayment:number
  years:number
  scenario:MortgageScenario
  bankId:string
  bank:string
  rate:number|null
  monthlyPayment:number
  totalPayment:number
  overpayment:number
}

const draftKey='geodom-mortgage-wizard-draft-v1'
const calculationsKey='geodom-mortgage-calculations-v1'
const allowedScenarios=new Set<MortgageScenario>(['newbuild','secondary','family','it'])
const allowedEmployment=new Set<MortgageEmployment>(['employee','self','business'])

function number(value:unknown,fallback=0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export function loadMortgageWizardDraft(sourcePrice:number):MortgageWizardDraft|null {
  try {
    const raw=localStorage.getItem(draftKey)
    if (!raw) return null
    const value=JSON.parse(raw) as Partial<MortgageWizardDraft>
    if (number(value.sourcePrice,-1) !== sourcePrice) return null
    if (!allowedScenarios.has(value.scenario as MortgageScenario)) return null
    if (!allowedEmployment.has(value.employment as MortgageEmployment)) return null
    const step=number(value.step,1)
    if (![1,2,3,4].includes(step)) return null
    return {
      sourcePrice,
      step:step as 1|2|3|4,
      scenario:value.scenario as MortgageScenario,
      bankId:typeof value.bankId === 'string' ? value.bankId : 'sber',
      propertyPrice:Math.max(300_000,number(value.propertyPrice,sourcePrice)),
      downPayment:Math.max(0,number(value.downPayment,0)),
      years:Math.min(30,Math.max(1,number(value.years,20))),
      monthlyIncome:Math.max(0,number(value.monthlyIncome,0)),
      existingPayments:Math.max(0,number(value.existingPayments,0)),
      employment:value.employment as MortgageEmployment,
      childrenCount:Math.max(1,Math.round(number(value.childrenCount,1))),
      youngestChildAge:value.youngestChildAge === null ? null : Math.max(0,number(value.youngestChildAge,3)),
      itAccredited:Boolean(value.itAccredited),
      updatedAt:typeof value.updatedAt === 'string' ? value.updatedAt : new Date().toISOString()
    }
  } catch {
    return null
  }
}

export function saveMortgageWizardDraft(draft:MortgageWizardDraft) {
  localStorage.setItem(draftKey,JSON.stringify(draft))
}

export function clearMortgageWizardDraft() {
  localStorage.removeItem(draftKey)
}

export function loadSavedMortgageCalculations():SavedMortgageCalculation[] {
  try {
    const parsed=JSON.parse(localStorage.getItem(calculationsKey) || '[]') as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item):item is SavedMortgageCalculation => {
      if (!item || typeof item !== 'object') return false
      const value=item as Partial<SavedMortgageCalculation>
      return typeof value.id === 'string'
        && typeof value.bank === 'string'
        && allowedScenarios.has(value.scenario as MortgageScenario)
        && Number.isFinite(value.apartmentPrice)
        && Number.isFinite(value.monthlyPayment)
    }).slice(0,10)
  } catch {
    return []
  }
}

export function saveMortgageCalculation(calculation:SavedMortgageCalculation) {
  const next=[calculation,...loadSavedMortgageCalculations().filter(item => item.id !== calculation.id)].slice(0,10)
  localStorage.setItem(calculationsKey,JSON.stringify(next))
  return next
}

export function deleteSavedMortgageCalculation(id:string) {
  const next=loadSavedMortgageCalculations().filter(item => item.id !== id)
  localStorage.setItem(calculationsKey,JSON.stringify(next))
  return next
}

export const mortgageWizardDraftStorageKey=draftKey
export const mortgageCalculationsStorageKey=calculationsKey
