import { getRiskColor } from '../utils/risk'

interface RiskGaugeProps {
  score: number  // 0-100
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

export default function RiskGauge({ score, label, size = 'md' }: RiskGaugeProps) {
  const pct = Math.min(100, Math.max(0, score))
  const category = pct < 25 ? 'LOW' : pct < 50 ? 'MODERATE' : pct < 75 ? 'HIGH' : 'EXTREME'
  const color = pct < 25 ? '#22c55e' : pct < 50 ? '#f59e0b' : pct < 75 ? '#f97316' : '#ef4444'

  const bars = 20
  const filled = Math.round((pct / 100) * bars)

  return (
    <div className="space-y-1">
      {label && <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>}
      <div className="flex items-center gap-2">
        <div className="flex gap-0.5">
          {Array.from({ length: bars }).map((_, i) => (
            <div
              key={i}
              className="w-1.5 rounded-sm transition-all"
              style={{
                height: size === 'sm' ? 12 : size === 'lg' ? 20 : 16,
                backgroundColor: i < filled ? color : '#1a2540',
                opacity: i < filled ? 1 : 0.4,
              }}
            />
          ))}
        </div>
        <div className="text-sm font-bold" style={{ color }}>
          {pct.toFixed(0)}
        </div>
      </div>
      <div className="text-xs font-mono" style={{ color }}>
        {category}
      </div>
    </div>
  )
}
