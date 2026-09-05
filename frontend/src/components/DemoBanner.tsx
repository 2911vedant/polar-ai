import { AlertTriangle } from 'lucide-react'

export default function DemoBanner() {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-950/40 border border-amber-800/40 rounded-lg text-xs text-amber-400">
      <AlertTriangle className="w-3 h-3 flex-shrink-0" />
      <span>
        <strong>DEMO / SIMULATION DATA</strong> — All displayed values are synthetically generated.
        Not for real navigation.
      </span>
    </div>
  )
}
