import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Database, ExternalLink, RefreshCw, CheckCircle, AlertTriangle, XCircle, Clock, Wifi, WifiOff } from 'lucide-react'
import { api } from '../services/api'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import LiveDataEngine from '../components/LiveDataEngine'
import type { FreshnessInfo } from '../types'

const STATUS_CONFIG: Record<string, { icon: any; cls: string; label: string }> = {
  LIVE:             { icon: CheckCircle,   cls: 'text-emerald-400 bg-emerald-950/40 border-emerald-700/40',  label: 'LIVE' },
  NEAR_REAL_TIME:   { icon: CheckCircle,   cls: 'text-emerald-300 bg-emerald-950/30 border-emerald-800/30',  label: 'NRT' },
  LATEST_AVAILABLE: { icon: Clock,         cls: 'text-yellow-400 bg-yellow-950/40 border-yellow-700/40',    label: 'LATEST' },
  STALE:            { icon: AlertTriangle, cls: 'text-orange-400 bg-orange-950/40 border-orange-700/40',   label: 'STALE' },
  OFFLINE:          { icon: WifiOff,       cls: 'text-red-400 bg-red-950/40 border-red-700/40',             label: 'OFFLINE' },
  DEMO:             { icon: AlertTriangle, cls: 'text-amber-400 bg-amber-950/40 border-amber-700/40',       label: 'DEMO' },
  UNKNOWN:          { icon: AlertTriangle, cls: 'text-slate-500 bg-polar-bg border-polar-border',           label: '?' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.UNKNOWN
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-bold ${cfg.cls}`}>
      <Icon className="w-3 h-3" />{cfg.label}
    </span>
  )
}

export default function DataSourcesPage() {
  const qc = useQueryClient()

  const { data: liveStatus, isLoading } = useQuery({
    queryKey: ['live-status'],
    queryFn: () => api.get('/api/live/status').then(r => r.data),
    refetchInterval: 15_000,
  })

  const { data: changes } = useQuery({
    queryKey: ['live-changes'],
    queryFn: () => api.get('/api/live/changes').then(r => r.data),
    refetchInterval: 60_000,
  })

  const { data: history } = useQuery({
    queryKey: ['live-history'],
    queryFn: () => api.get('/api/live/history?limit=10').then(r => r.data),
    refetchInterval: 60_000,
  })

  const triggerMut = useMutation({
    mutationFn: () => api.post('/api/live/trigger').then(r => r.data),
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['live-status'] })
        qc.invalidateQueries({ queryKey: ['live-changes'] })
      }, 5000)
    },
  })

  if (isLoading) return <LoadingSpinner message="Loading data sources..." />

  const sources: FreshnessInfo[] = liveStatus?.sources?.sources || []
  const creds = liveStatus?.credentials || {}
  const dataMode = liveStatus?.data_mode || 'live'
  const isDemo = dataMode === 'demo'

  // Separate free sources from credentialed
  const freeSources  = sources.filter(s => ['sea_ice','icebergs','weather','ocean'].includes(s.source_id))
  const credSources  = sources.filter(s => ['satellite','ais'].includes(s.source_id))
  const infraSources = sources.filter(s => ['database'].includes(s.source_id))

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Database}
        title="Data Sources"
        subtitle="Live status of all Antarctic data feeds — updated automatically every hour"
        showDemoBanner={isDemo}
        actions={
          <button
            onClick={() => triggerMut.mutate()}
            disabled={triggerMut.isPending}
            className="btn-primary flex items-center gap-1.5 text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${triggerMut.isPending ? 'animate-spin' : ''}`} />
            Update Now
          </button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: source tables */}
        <div className="xl:col-span-2 space-y-5">

          {/* Summary row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Total Sources',  value: sources.length,                                        color: 'text-white' },
              { label: 'Connected',      value: sources.filter(s => ['LIVE','NEAR_REAL_TIME','LATEST_AVAILABLE'].includes(s.status)).length, color: 'text-emerald-400' },
              { label: 'Offline',        value: sources.filter(s => s.status === 'OFFLINE').length,    color: 'text-red-400' },
              { label: 'Demo',           value: sources.filter(s => s.status === 'DEMO').length,       color: 'text-amber-400' },
            ].map(s => (
              <div key={s.label} className="card text-center">
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-slate-500">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Free sources */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Wifi className="w-4 h-4 text-emerald-400" />
              Free Sources — No Credentials Required
            </div>
            <SourceTable sources={freeSources} />
          </div>

          {/* Credentialed sources */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-polar-accent" />
              Credentialed Sources
            </div>
            <SourceTable sources={credSources} />
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[
                { key: 'copernicus_satellite', label: 'Copernicus Sentinel-1', hint: 'COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET', url: 'https://dataspace.copernicus.eu/' },
                { key: 'ais_vessel',           label: 'AIS Vessel Tracking',  hint: 'AIS_PROVIDER + AIS_API_KEY', url: 'https://aisstream.io/' },
              ].map(({ key, label, hint, url }) => {
                const active = !!(creds as any)[key]
                return (
                  <div key={key} className={`p-2.5 rounded-lg border text-xs ${active ? 'bg-emerald-950/30 border-emerald-800/30' : 'bg-polar-bg border-polar-border'}`}>
                    <div className={`font-semibold mb-1 ${active ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {active ? '✓' : '○'} {label}
                    </div>
                    {!active && (
                      <>
                        <div className="text-slate-600 font-mono text-xs">{hint}</div>
                        <a href={url} target="_blank" rel="noopener noreferrer"
                           className="text-polar-accent hover:underline mt-1 block">
                          Register free →
                        </a>
                      </>
                    )}
                    {active && <div className="text-emerald-600">Configured ✓</div>}
                  </div>
                )
              })}
            </div>
          </div>

          {/* What changed */}
          {changes?.changes?.length > 0 && (
            <div className="card">
              <div className="text-sm font-semibold text-white mb-3">
                Last Hour Changes
                {changes.last_run && (
                  <span className="ml-2 text-xs text-slate-500 font-normal">
                    {new Date(changes.last_run).toLocaleTimeString()}
                  </span>
                )}
              </div>
              <div className="space-y-2">
                {changes.changes.map((c: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    {c.type === 'updated'   && <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />}
                    {c.type === 'error'     && <XCircle     className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" />}
                    {c.type === 'no_change' && <Clock       className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />}
                    <div>
                      <span className="font-mono text-slate-400 mr-2">{c.source_id}</span>
                      <span className="text-slate-400">{c.message}</span>
                      {c.records > 0 && (
                        <span className="ml-2 text-polar-accent">{c.records} records</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Update history */}
          {history?.runs?.length > 0 && (
            <div className="card">
              <div className="text-sm font-semibold text-white mb-3">Update History</div>
              <div className="space-y-1">
                {history.runs.slice().reverse().map((run: any) => (
                  <div key={run.run_id} className="flex items-center gap-3 text-xs py-1 border-b border-polar-border/50">
                    <span className="text-slate-600 font-mono w-6">#{run.run_number}</span>
                    <span className="text-slate-400 font-mono w-20">
                      {new Date(run.started_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
                    </span>
                    <span className={`font-mono ${run.status === 'success' ? 'text-emerald-400' : run.status === 'partial' ? 'text-yellow-400' : 'text-red-400'}`}>
                      {run.status}
                    </span>
                    <span className="text-slate-500">
                      {run.succeeded}✓ {run.failed > 0 ? `${run.failed}✗` : ''} {run.skipped > 0 ? `${run.skipped}—` : ''}
                    </span>
                    <span className="text-slate-600 ml-auto">{run.duration_seconds?.toFixed(1)}s</span>
                    <span className="text-slate-600 capitalize">{run.triggered_by}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: LiveDataEngine */}
        <div>
          <div className="card">
            <LiveDataEngine compact={false} />
          </div>
        </div>
      </div>
    </div>
  )
}

function SourceTable({ sources }: { sources: FreshnessInfo[] }) {
  if (!sources.length) return <div className="text-xs text-slate-500 py-2">No sources</div>
  return (
    <div className="divide-y divide-polar-border">
      {sources.map(src => (
        <div key={src.source_id} className="py-2.5 flex items-center gap-3">
          <div className="w-28 flex-shrink-0">
            <div className="text-xs text-white font-medium truncate">{src.source_name}</div>
            <div className="text-xs text-slate-600 truncate">{src.source}</div>
          </div>
          <StatusBadge status={src.status} />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-slate-500 truncate">
              {src.status === 'OFFLINE' && src.last_error
                ? `Error: ${src.last_error.slice(0, 60)}`
                : src.age_human
                  ? `Updated ${src.age_human}`
                  : src.status === 'OFFLINE'
                    ? 'Not yet connected'
                    : ''}
            </div>
          </div>
          <div className="text-xs text-slate-600 font-mono flex-shrink-0">
            {src.record_count != null ? `${src.record_count.toLocaleString()} rec` : ''}
          </div>
        </div>
      ))}
    </div>
  )
}
