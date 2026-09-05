import { useState, useEffect } from 'react'
import { Bell, X, AlertTriangle, Info, AlertOctagon } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAlerts, acknowledgeAlert, createAlertsEventSource } from '../services/api'
import type { NavAlert } from '../types'

const LEVEL_ICON: Record<string, any> = {
  INFO: Info, WARNING: AlertTriangle, DANGER: AlertTriangle, CRITICAL: AlertOctagon,
}
const LEVEL_COLOR: Record<string, string> = {
  INFO: 'text-sky-400', WARNING: 'text-yellow-400', DANGER: 'text-orange-400', CRITICAL: 'text-red-400',
}
const LEVEL_BG: Record<string, string> = {
  INFO: 'bg-sky-950/50 border-sky-800/30',
  WARNING: 'bg-yellow-950/50 border-yellow-800/30',
  DANGER: 'bg-orange-950/50 border-orange-800/30',
  CRITICAL: 'bg-red-950/50 border-red-800/30',
}

export default function AlertBell() {
  const [open, setOpen] = useState(false)
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => fetchAlerts(20),
    refetchInterval: 30_000,
  })

  const ackMut = useMutation({
    mutationFn: acknowledgeAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  // SSE for real-time alerts
  useEffect(() => {
    const es = createAlertsEventSource(() => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
    })
    return () => es.close()
  }, [])

  const alerts: NavAlert[] = data?.alerts || []
  const unread = data?.unread_count || 0

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative p-2 rounded-lg hover:bg-polar-border transition-colors"
      >
        <Bell className="w-4 h-4 text-slate-400" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-white text-xs flex items-center justify-center font-bold">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-8 w-80 bg-polar-card border border-polar-border rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-polar-border">
            <span className="text-sm font-semibold text-white">Navigation Alerts</span>
            <button onClick={() => setOpen(false)}><X className="w-4 h-4 text-slate-500" /></button>
          </div>
          <div className="max-h-72 overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-slate-500">No active alerts</div>
            ) : (
              alerts.map(alert => {
                const Icon = LEVEL_ICON[alert.level] || Info
                const color = LEVEL_COLOR[alert.level] || 'text-slate-400'
                const bg = LEVEL_BG[alert.level] || 'bg-polar-bg border-polar-border'
                return (
                  <div key={alert.id} className={`mx-2 my-1.5 p-2.5 rounded-lg border text-xs ${bg} ${alert.acknowledged ? 'opacity-50' : ''}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${color}`} />
                        <span className={`font-semibold ${color}`}>{alert.title}</span>
                      </div>
                      {!alert.acknowledged && (
                        <button
                          onClick={() => ackMut.mutate(alert.id)}
                          className="text-slate-600 hover:text-slate-300 flex-shrink-0"
                        >✓</button>
                      )}
                    </div>
                    <p className="mt-1 text-slate-400 leading-relaxed">{alert.message}</p>
                    <p className="mt-1 text-slate-600">{alert.age_seconds < 60 ? `${alert.age_seconds.toFixed(0)}s ago` : `${(alert.age_seconds / 60).toFixed(0)}m ago`}</p>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
