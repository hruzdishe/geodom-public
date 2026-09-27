import { describe,expect,it } from 'vitest'
import { mortgageProgramEligibility,resolveMortgageProgram } from './mortgagePrograms'

describe('mortgage programs',() => {
  it('uses the current family-mortgage terms before October 2026 change',() => {
    const terms=resolveMortgageProgram('family',{childrenCount:1,youngestChildAge:3,now:new Date('2026-09-26T12:00:00+03:00')})
    expect(terms.rate).toBe(6)
    expect(terms.maxAmount).toBe(6_000_000)
    expect(terms.maxYears).toBe(30)
  })

  it('switches family terms after 1 October 2026 based on number of children',() => {
    const one=resolveMortgageProgram('family',{childrenCount:1,youngestChildAge:4,now:new Date('2026-10-02T12:00:00+03:00')})
    const five=resolveMortgageProgram('family',{childrenCount:5,youngestChildAge:2,now:new Date('2026-10-02T12:00:00+03:00')})
    expect(one.rate).toBe(10)
    expect(one.maxAmount).toBe(6_000_000)
    expect(five.rate).toBe(2)
    expect(five.maxAmount).toBe(10_000_000)
    expect(five.maxYears).toBe(15)
  })

  it('marks the Far East program unavailable for the Krasnoyarsk calculator',() => {
    const terms=resolveMortgageProgram('far-east',{childrenCount:0,youngestChildAge:null,apartmentArea:70})
    const eligibility=mortgageProgramEligibility(terms,8_000_000,2_000_000,20)
    expect(terms.maxAmount).toBe(9_000_000)
    expect(eligibility.eligible).toBe(false)
  })
})
