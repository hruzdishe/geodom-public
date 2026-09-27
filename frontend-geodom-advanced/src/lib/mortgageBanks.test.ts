import { describe,expect,it } from 'vitest'
import { KRASNOYARSK_MORTGAGE_BANKS,mortgageOfferEligibility } from './mortgageBanks'

describe('Krasnoyarsk mortgage snapshot',() => {
  it('keeps the complete 19-bank secondary-housing demo directory',() => {
    expect(KRASNOYARSK_MORTGAGE_BANKS).toHaveLength(19)
    expect(new Set(KRASNOYARSK_MORTGAGE_BANKS.map(item => item.id)).size).toBe(19)
  })

  it('checks down payment amount term and missing-rate constraints',() => {
    const tbank=KRASNOYARSK_MORTGAGE_BANKS.find(item => item.id === 'tbank')!
    expect(mortgageOfferEligibility(tbank,10_000_000,2_000_000,20).eligible).toBe(true)
    expect(mortgageOfferEligibility(tbank,10_000_000,1_000_000,20).eligible).toBe(false)

    const domrf=KRASNOYARSK_MORTGAGE_BANKS.find(item => item.id === 'domrf')!
    expect(mortgageOfferEligibility(domrf,10_000_000,5_000_000,20).eligible).toBe(false)
  })
})
