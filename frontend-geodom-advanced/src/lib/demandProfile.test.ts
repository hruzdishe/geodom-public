// @vitest-environment jsdom
import { beforeEach,describe,expect,it } from 'vitest'
import { buildSharedDemandProfile,loadSharedDemandProfile,revokeSharedDemandProfile,saveSharedDemandProfile,sharedDemandProfileToLead } from './demandProfile'
import { defaultCatalogFilters,defaultPreferences } from './preferences'

beforeEach(() => localStorage.clear())

describe('shared demand profile',() => {
  it('builds a lead profile from current GeoDom preferences and catalog filters',() => {
    const profile=buildSharedDemandProfile({
      current:null,
      user:{id:'u1',login:'ivan'},
      contact:'+7 900 000-00-00',
      consentToContact:true,
      preferences:{...defaultPreferences,budget_max:8_000_000,max_commute_minutes:30,priorities:{...defaultPreferences.priorities,parks:5}},
      filters:{...defaultCatalogFilters,district:'Советский',rooms:2}
    })
    expect(profile.budgetMax).toBe(8_000_000)
    expect(profile.districts).toEqual(['Советский'])
    expect(profile.roomsMin).toBe(2)
    expect(profile.roomsMax).toBe(2)
    expect(profile.priorities).toContain('Парки')
  })

  it('persists consent and can revoke it without deleting the profile',() => {
    const profile=buildSharedDemandProfile({
      current:null,
      user:{id:'u1',login:'ivan'},
      contact:'@ivan',
      consentToContact:true,
      preferences:defaultPreferences,
      filters:defaultCatalogFilters
    })
    saveSharedDemandProfile(profile)
    expect(loadSharedDemandProfile()?.consentToContact).toBe(true)
    revokeSharedDemandProfile()
    expect(loadSharedDemandProfile()?.consentToContact).toBe(false)
  })

  it('converts only the shared profile shape into a Pro lead',() => {
    const profile=buildSharedDemandProfile({
      current:null,
      user:{id:'u1',login:'ivan'},
      contact:'ivan@example.test',
      consentToContact:true,
      preferences:defaultPreferences,
      filters:defaultCatalogFilters
    })
    const lead=sharedDemandProfileToLead(profile)
    expect(lead.source).toBe('local')
    expect(lead.contact).toBe('ivan@example.test')
  })
})
