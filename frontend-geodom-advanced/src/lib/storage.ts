const localKeys = [
  'demo-apartments-v1',
  'demo-users-v1',
  'saved-apartments-v1',
  'demo-events-v1',
  'recommendation-preferences-v1',
  'catalog-filters-v1',
  'last-recommendation-v1'
]
const sessionKeys = ['session-v1']

export function migrateLegacyStorage() {
  for (const [store,keys] of [[localStorage,localKeys],[sessionStorage,sessionKeys]] as const) {
    for (const suffix of keys) {
      const oldValue = store.getItem(`sreda-${suffix}`)
      if (oldValue !== null && store.getItem(`geodom-${suffix}`) === null) store.setItem(`geodom-${suffix}`,oldValue)
    }
  }

  const legacyRecommendation = sessionStorage.getItem('geodom-last-recommendation-v1') || sessionStorage.getItem('sreda-last-recommendation-v1')
  if (legacyRecommendation !== null && localStorage.getItem('geodom-last-recommendation-v1') === null) {
    localStorage.setItem('geodom-last-recommendation-v1',legacyRecommendation)
  }
}
