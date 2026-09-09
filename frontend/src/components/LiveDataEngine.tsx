/**
 * POLAR-AI Live Data Engine Component
 *
 * Shows:
 *  - Current data mode (LIVE / DEMO)
 *  - Last update time
 *  - Countdown to next update
 *  - "UPDATE NOW" button
 *  - Per-source freshness dots
 *  - Update log (last N completed tasks)
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Activity, Clock, CheckCircle, XCircle, AlertTriangle, Minus } from 'lucide-react'
import { fetchSystemStatus, api, WS_BASE } from '../services/api'
import type { FreshnessInfo } from '../types'

interface LiveEngineProps {
  onDataRefresh?: (sources: string[]) => void
  compact?: boolean
}

const STATUS_DOT: Record<string, string> = {
  LIVE:             'bg-emerald-400 animate-pulse',
  NEAR_REAL_TIME:   'bg-emerald-400',
  LATEST_AVAILABLE: 'bg-yellow-400',
  STALE:            'bg-orange-400',
  OFFLINE:          'bg-red-500',
  DEMO:             'bg-amber-400',
  UNKNOWN:          'bg-slate-500',
}

const STATUS_TEXT: Record<string, string> = {
  LIVE:             'text-emerald-400',
  NEAR_REAL_TIME:   'text-emerald-300',
  LATEST_AVAILABLE: 'text-yellow-400',
  STALE:            'text-orange-400',
  OFFLINE:          'text-red-400',
  DEMO:             'text-amber-400',
  UNKNOWN:          'text-slate-500',
}

function pad(n: number) { return String(Math.floor(n)).padStart(2, '0') }

function Countdown({ secondsRemaining }: { secondsRemaining: number }) {
  const [secs, setSecs] = useState(secondsRemaining)

  useEffect(() => { setSecs(secondsRemaining) }, [secondsRemaining])

  useEffect(() => {
    if (secs <= 0) return
    const t = setTimeout(() => setSecs(s => Math.max(0, s - 1)), 1000)
    return () => clearTimeout(t)
  }, [secs])

  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  const color = secs < 60 ? 'text-amber-400' : 'text-slate-300'

  return (
    <span className={`font-mono text-xs tabular-nums ${color}`}>
      {h > 0 ? `${pad(h)}:` : ''}{pad(m)}:{pad(s)}
    </span>
  )
}

export default function LiveDataEngine({ onDataRefresh, compact = false }: LiveEngineProps) {
  const [updateLog, setUpdateLog] = useState<Array<{
    time: string; source: string; status: string; note: string
  }>>([])
  const [isUpdating, setIsUpdating] = useState(false)
  const [lastUpdateTime, setLastUpdateTime] = useState<string | null>(null)
  const [nextUpdateSecs, setNextUpdateSecs] = useState<number>(3600)
  const wsRef = useRef<WebSocket | null>(null)
  const qc = useQueryClient()

  const { data: status } = useQuery({
    queryKey: ['live-status'],
    queryFn: () => api.get('/api/live/status').then(r => r.data),
    refetchInterval: 30_000,
  })

  // Sync countdown from server
  useEffect(() => {
    if (status?.seconds_to_next_update != null) {
      setNextUpdateSecs(Math.max(0, Math.round(status.seconds_to_next_update)))
    }
    if (status?.current_run?.started_at) {
      setLastUpdateTime(status.current_run.started_at)
    }
  }, [status])

  // /ws/live WebSocket — receives events when data updates
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/api/ws/live`)

    ws.onopen = () => {
      console.log('[ws/live] connected')
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        handleWsEvent(msg)
      } catch {}
    }

    ws.onerror = () => console.warn('[ws/live] error')
    ws.onclose = () => {}

    wsRef.current = ws
    return () => { ws.close() }
  }, [])

  const handleWsEvent = useCallback((msg: any) => {
    const event = msg.event

    if (event === 'DATA_REFRESH_COMPLETE') {
      setIsUpdating(false)
      setLastUpdateTime(msg.timestamp)

      // Reset countdown
      if (status?.update_interval_minutes) {
        setNextUpdateSecs(status.update_interval_minutes * 60)
      }

      // Invalidate all relevant queries so components auto-refresh
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['icebergs'] })
      qc.invalidateQueries({ queryKey: ['sea-ice-low'] })
      qc.invalidateQueries({ queryKey: ['sea-ice-current'] })
      qc.invalidateQueries({ queryKey: ['ocean-current'] })
      qc.invalidateQueries({ queryKey: ['weather-current'] })
      qc.invalidateQueries({ queryKey: ['vessel-position'] })
      qc.invalidateQueries({ queryKey: ['vessel-track-1h'] })
      qc.invalidateQueries({ queryKey: ['satellite-latest'] })
      qc.invalidateQueries({ queryKey: ['live-status'] })
      qc.invalidateQueries({ queryKey: ['data-sources'] })
      qc.invalidateQueries({ queryKey: ['system-status'] })

      // Build update log from tasks
      const tasks = msg.tasks || {}
      const now = new Date().toLocaleTimeString()
      const entries = Object.entries(tasks).map(([src, t]: any) => ({
        time: now,
        source: src,
        status: t.status,
        note: t.note || t.error || '',
      }))
      setUpdateLog(prev => [...entries, ...prev].slice(0, 40))

      if (onDataRefresh) onDataRefresh(msg.sources_updated || [])
    }

    if (event === 'SATELLITE_UPDATED') qc.invalidateQueries({ queryKey: ['satellite-latest'] })
    if (event === 'SEA_ICE_UPDATED')   qc.invalidateQueries({ queryKey: ['sea-ice-current'] })
    if (event === 'ICEBERGS_UPDATED')  qc.invalidateQueries({ queryKey: ['icebergs'] })
    if (event === 'WEATHER_UPDATED')   qc.invalidateQueries({ queryKey: ['weather-current'] })
    if (event === 'OCEAN_UPDATED')     qc.invalidateQueries({ queryKey: ['ocean-current'] })
    if (event === 'VESSEL_UPDATED')    {
      qc.invalidateQueries({ queryKey: ['vessel-position'] })
      qc.invalidateQueries({ queryKey: ['vessel-track-1h'] })
    }
    if (event === 'RISK_UPDATED')      qc.invalidateQueries({ queryKey: ['dashboard'] })
  }, [qc, onDataRefresh, status])

  const triggerMut = useMutation({
    mutationFn: () => api.post('/api/live/trigger').then(r => r.data),
    onMutate: () => setIsUpdating(true),
    onSuccess: () => {
      setUpdateLog(prev => [{
        time: new Date().toLocaleTimeString(),
        source: 'system',
        status: 'triggered',
        note: 'Manual update triggered',
      }, ...prev])
    },
    onError: () => setIsUpdating(false),
  })

  const dataMode = status?.data_mode || 'live'
  const isDemo   = dataMode === 'demo'
  const sources: FreshnessInfo[] = status?.sources?.sources || []

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isDemo ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
        <span className={`text-xs font-mono font-bold ${isDemo ? 'text-amber-400' : 'text-emerald-400'}`}>
          {isDemo ? 'DEMO' : 'LIVE'}
        </span>
        {!isDemo && nextUpdateSecs > 0 && (
          <span className="text-xs text-slate-500">
            next: <Countdown secondsRemaining={nextUpdateSecs} />
          </span>
        )}
        <button
          onClick={() => triggerMut.mutate()}
          disabled={isUpdating || triggerMut.isPending}
          className="p-1 rounded hover:bg-polar-border transition-colors"
          title="Update Now"
        >
          <RefreshCw className={`w-3 h-3 text-slate-500 hover:text-white ${(isUpdating || triggerMut.isPending) ? 'animate-spin' : ''}`} />
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className={`w-4 h-4 ${isDemo ? 'text-amber-400' : 'text-emerald-400'}`} />
          <span className="text-sm font-semibold text-white">Data Engine</span>
          <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
            isDemo
              ? 'text-amber-400 bg-amber-950/40 border-amber-700'
              : 'text-emerald-400 bg-emerald-950/40 border-emerald-700'
          }`}>
            {isDemo ? 'DEMO MODE' : '● LIVE'}
          </span>
        </div>
        <button
          onClick={() => triggerMut.mutate()}
          disabled={isUpdating || triggerMut.isPending}
          className="btn-secondary flex items-center gap-1.5 text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${(isUpdating || triggerMut.isPending) ? 'animate-spin' : ''}`} />
          {isUpdating ? 'Updating…' : 'Update Now'}
        </button>
      </div>

      {/* Timing */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="card text-center py-2">
          <div className="text-slate-500 mb-0.5">Last Update</div>
          <div className="text-white font-mono">
            {lastUpdateTime
              ? new Date(lastUpdateTime).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
              : '—'}
          </div>
        </div>
        <div className="card text-center py-2">
          <div className="text-slate-500 mb-0.5">Next In</div>
          <div className="flex items-center justify-center">
            {nextUpdateSecs > 0
              ? <Countdown secondsRemaining={nextUpdateSecs} />
              : <span className="text-amber-400 font-mono text-xs animate-pulse">updating...</span>}
          </div>
        </div>
        <div className="card text-center py-2">
          <div className="text-slate-500 mb-0.5">Interval</div>
          <div className="text-white font-mono">{status?.update_interval_minutes || 60}m</div>
        </div>
      </div>

      {/* Source status grid */}
      {sources.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-slate-600 uppercase tracking-wider">Source Status</div>
          <div className="grid grid-cols-2 gap-1">
            {sources.filter(s => s.source_id !== 'database').map(src => (
              <div key={src.source_id} className="flex items-center gap-1.5 py-1 px-2 rounded bg-polar-bg border border-polar-border">
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[src.status] || STATUS_DOT.UNKNOWN}`} />
                <span className="text-xs text-slate-400 truncate flex-1">
                  {src.source_name.replace('Sea Ice — ', '').replace('Iceberg Tracking — ', '').replace('Weather — ', '').replace('Ocean — ', '')}
                </span>
                <span className={`text-xs font-mono ${STATUS_TEXT[src.status] || STATUS_TEXT.UNKNOWN}`}>
                  {src.status === 'NEAR_REAL_TIME' ? 'NRT' :
                   src.status === 'LATEST_AVAILABLE' ? 'LATEST' :
                   src.age_human && src.status !== 'OFFLINE' && src.status !== 'DEMO' ? src.age_human :
                   src.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Update log */}
      {updateLog.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-slate-600 uppercase tracking-wider">Last Update Log</div>
          <div className="max-h-48 overflow-y-auto space-y-0.5">
            {updateLog.slice(0, 16).map((entry, i) => (
              <div key={i} className="flex items-center gap-2 text-xs py-0.5">
                <span className="text-slate-600 font-mono w-14 flex-shrink-0">{entry.time}</span>
                {entry.status === 'success' ?
                  <CheckCircle className="w-3 h-3 text-emerald-400 flex-shrink-0" /> :
                  entry.status === 'failed' ?
                  <XCircle className="w-3 h-3 text-red-400 flex-shrink-0" /> :
                  entry.status === 'skipped' ?
                  <Minus className="w-3 h-3 text-slate-500 flex-shrink-0" /> :
                  <AlertTriangle className="w-3 h-3 text-amber-400 flex-shrink-0" />}
                <span className="text-slate-400 font-mono w-16 flex-shrink-0">{entry.source}</span>
                <span className="text-slate-500 truncate">{entry.note.slice(0, 60)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {isDemo && (
        <div className="p-2.5 bg-amber-950/40 border border-amber-800/30 rounded-lg text-xs text-amber-500">
          <strong>DEMO MODE</strong> — Synthetic data (seed=42). Set <code className="text-amber-300">DATA_MODE=live</code> in .env for real data.
        </div>
      )}
    </div>
  )
}
