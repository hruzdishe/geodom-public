import { describe,expect,it } from 'vitest'
import { calculateRentVsBuy,type RentVsBuyInput } from './RentVsBuyCalculator'

const baseline:RentVsBuyInput={
  apartmentPrice:6_000_000,downPayment:6_000_000,annualRate:0,years:5,mortgageYears:20,
  monthlyRent:30_000,rentGrowthPercent:0,homeGrowthPercent:0,maintenancePercent:0,
  investmentReturnPercent:0,purchaseCostsPercent:0,saleCostsPercent:0
}

describe('rent vs buy model',() => {
  it('counts the home and monthly savings when buying without a mortgage',() => {
    const result=calculateRentVsBuy(baseline)
    expect(result.buyerNetWorth).toBe(7_800_000)
    expect(result.renterNetWorth).toBe(6_000_000)
    expect(result.difference).toBe(1_800_000)
    expect(result.totalRentPaid).toBe(1_800_000)
    expect(result.remainingMortgage).toBe(0)
  })

  it('does not confuse repaid principal with lost money',() => {
    const result=calculateRentVsBuy({...baseline,apartmentPrice:1_200_000,downPayment:0,monthlyRent:0,mortgageYears:1,years:1})
    expect(result.buyerNetWorth).toBe(1_200_000)
    expect(result.renterNetWorth).toBe(1_200_000)
    expect(result.difference).toBe(0)
  })

  it('retains debt exceeding a falling home value, including selling fees',() => {
    const result=calculateRentVsBuy({...baseline,apartmentPrice:1_000_000,downPayment:0,monthlyRent:0,mortgageYears:30,years:1,homeGrowthPercent:-50,saleCostsPercent:2})
    expect(result.futureHomeValue).toBeCloseTo(500_000,5)
    expect(result.remainingMortgage).toBeCloseTo(966_666.666667,5)
    expect(result.buyerNetWorth).toBeCloseTo(-476_666.666667,5)
    expect(result.difference).toBeCloseTo(-510_000,5)
  })

  it('uses the entered rent in the first month before applying growth',() => {
    const result=calculateRentVsBuy({...baseline,years:1/12,rentGrowthPercent:12})
    expect(result.totalRentPaid).toBe(30_000)
    expect(result.buyerPortfolio).toBe(30_000)
  })

  it('compounds annual growth monthly without adding an extra month',() => {
    const result=calculateRentVsBuy({...baseline,years:1,homeGrowthPercent:10,rentGrowthPercent:12})
    const monthlyGrowth=Math.pow(1.12,1/12)-1
    expect(result.futureHomeValue).toBeCloseTo(6_600_000,5)
    expect(result.totalRentPaid).toBeCloseTo(30_000*.12/monthlyGrowth,5)
  })

  it('stops mortgage payments at maturity and invests the owner saving afterwards',() => {
    const result=calculateRentVsBuy({...baseline,apartmentPrice:1_200_000,downPayment:0,monthlyRent:50_000,mortgageYears:1,years:2})
    expect(result.remainingMortgage).toBe(0)
    expect(result.totalMortgagePaid).toBe(1_200_000)
    expect(result.renterPortfolio).toBe(600_000)
    expect(result.buyerPortfolio).toBe(600_000)
    expect(result.difference).toBe(1_200_000)
  })

  it('starts both options with equal cash and deducts all specified expenses',() => {
    const result=calculateRentVsBuy({...baseline,apartmentPrice:1_000_000,downPayment:1_000_000,monthlyRent:0,years:1,purchaseCostsPercent:1,saleCostsPercent:2,maintenancePercent:1})
    expect(result.purchaseCosts).toBe(10_000)
    expect(result.saleCosts).toBe(20_000)
    expect(result.totalMaintenancePaid).toBeCloseTo(10_000)
    expect(result.buyerNetWorth).toBe(980_000)
    expect(result.renterNetWorth).toBeCloseTo(1_020_000)
    expect(result.difference).toBeCloseTo(-40_000)
  })

  it('accrues return on initial capital but not on the current month contribution',() => {
    const result=calculateRentVsBuy({...baseline,years:1,monthlyRent:0,investmentReturnPercent:10})
    expect(result.renterPortfolio).toBeCloseTo(6_600_000,5)
    expect(result.difference).toBeCloseTo(-600_000,5)
  })

  it('matches a hand-calculated one-month annuity amortization',() => {
    const result=calculateRentVsBuy({...baseline,apartmentPrice:1_200,downPayment:0,annualRate:12,mortgageYears:1,years:1/12,monthlyRent:0})
    // 1200 principal; 12 interest; 106.618546 monthly payment.
    expect(result.monthlyMortgage).toBeCloseTo(106.618546,6)
    expect(result.remainingMortgage).toBeCloseTo(1105.381454,6)
    expect(result.difference).toBeCloseTo(-12,8)
  })

  it('can favor renting for a short horizon and buying for a longer one',() => {
    const scenario={...baseline,apartmentPrice:1_000_000,downPayment:1_000_000,monthlyRent:10_000,purchaseCostsPercent:10,saleCostsPercent:10}
    expect(calculateRentVsBuy({...scenario,years:1}).difference).toBeCloseTo(-80_000)
    expect(calculateRentVsBuy({...scenario,years:5}).difference).toBeCloseTo(400_000)
  })

  it.each<Partial<RentVsBuyInput>>([
    {monthlyRent:NaN},{annualRate:Infinity},{years:0},{years:1000},{mortgageYears:0},
    {downPayment:7_000_000},{downPayment:-1},{monthlyRent:-1},{annualRate:-1},
    {homeGrowthPercent:-100},{investmentReturnPercent:101},{purchaseCostsPercent:-1},{saleCostsPercent:101}
  ])('rejects invalid input instead of displaying a misleading verdict: %j',patch => {
    expect(() => calculateRentVsBuy({...baseline,...patch})).toThrow(RangeError)
  })
})
