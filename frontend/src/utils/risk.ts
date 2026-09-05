export type RiskCategory = 'low' | 'moderate' | 'high' | 'extreme'

export function getRiskColor(category: string): string {
  switch (category?.toLowerCase()) {
    case 'low':      return '#22c55e'
    case 'moderate': return '#f59e0b'
    case 'high':     return '#f97316'
    case 'extreme':  return '#ef4444'
    default:         return '#64748b'
  }
}

export function getRiskBadgeClass(category: string): string {
  switch (category?.toLowerCase()) {
    case 'low':      return 'risk-badge-low'
    case 'moderate': return 'risk-badge-moderate'
    case 'high':     return 'risk-badge-high'
    case 'extreme':  return 'risk-badge-extreme'
    default:         return 'risk-badge-low'
  }
}

export function getSicColor(concentration: number): string {
  if (concentration < 0.15) return '#1e3a5f'        // open water - deep blue
  if (concentration < 0.40) return '#3b82f6'        // low ice - blue
  if (concentration < 0.65) return '#93c5fd'        // moderate - light blue
  if (concentration < 0.85) return '#e2e8f0'        // high - pale
  return '#f8fafc'                                   // consolidated - white
}

export function getSicCategory(sic: number): string {
  if (sic < 0.15) return 'Open Water'
  if (sic < 0.40) return 'Low Ice'
  if (sic < 0.65) return 'Moderate'
  if (sic < 0.85) return 'High'
  return 'Consolidated'
}

export function formatRiskScore(score: number): string {
  return `${(score * 100).toFixed(0)}/100`
}

export function getRiskLabel(score: number): RiskCategory {
  if (score < 0.25) return 'low'
  if (score < 0.50) return 'moderate'
  if (score < 0.75) return 'high'
  return 'extreme'
}
