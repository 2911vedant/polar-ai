import { useQuery } from '@tanstack/react-query'
import { Database, ExternalLink, RefreshCw, CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react'
import { fetchDataSources, fetchSystemStatus, refreshSatellite } from '../services/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import type { DataSource } from '../types'

const STATUS_CONFIG: Record<string, { icon: any; cls: string; label: string }> = {
  LIVE:             { icon: CheckCircle,  cls: 'text-emerald-400 bg-emerald-950/40 border-emerald-700/40', label: 'LIVE' },
  NEAR_REAL_TIME:   { icon: CheckCircle,  cls: 'text-emerald-400 bg-emerald-950/30 border-emerald-800/30', label: 'NRT' },
  LATEST_AVAILABLE: { icon: Clock,        cls: 'text-yellow-400 bg-yellow-950/40 border-yellow-700/40',   label: 'LATEST' },
  STALE:            { icon: AlertTriangle,cls: 'text-orange-400 bg-orange-950/40 border-orange-700/40',   label: 'STALE' },
  OFFLINE:          { icon: XCircle,      cls: 'text-red-400 bg-red-950/40 border-red-700/40',            label: 'OFFLINE' },
  DEMO:             { icon: AlertTriangle,cls: 'text-amber-400 bg-amber-950/40 border-amber-700/40',      label: 'DEMO' },
  UNKNOWN:          { icon: AlertTriangle,cls: 'text-slate-500 bg-polar-bg border-polar-border',          label: '?' },
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
  const { data, isLoading } = useQuery({ queryKey: ['data-sources'], queryFn: fetchDataSources, staleTime: 30_000 })
  const { data: status } = useQuery({ queryKey: ['system-status'], queryFn: fetchSystemStatus, refetchInterval: 30_000 })

  const satRefresh = useMutation({
    mutationFn: refreshSatellite,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['data-sources'] }),
  })

  if (isLoading) return <LoadingSpinner message="Loading data sources..." />

  const sources: DataSource[] = data?.sources ?? []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader icon={Database} title="Data Sources"
        subtitle="Status of all Antarctic data feeds — real-time freshness monitoring"
        showDemoBanner={false} />

      {/* Summary row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Total Sources',  value: data?.summary?.total ?? 0,     color: 'text-white' },
          { label: 'Connected',      value: data?.summary?.connected ?? 0,  color: 'text-emerald-400' },
          { label: 'Demo Mode',      value: data?.summary?.demo ?? 0,       color: 'text-amber-400' },
          { label: 'Offline',        value: data?.summary?.offline ?? 0,    color: 'text-red-400' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-slate-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Credentials status */}
      {status?.credentials && (
        <div className="card">
          <div className="text-sm font-semibold text-white mb-3">Credential Status</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {[
              { key: 'copernicus', label: 'Copernicus Data Space', hint: 'COPERNICUS_CLIENT_ID / SECRET' },
              { key: 'ais',        label: 'AIS Vessel Tracking',   hint: 'AIS_PROVIDER / AIS_API_KEY' },
              { key: 'cmems',      label: 'Copernicus Marine',     hint: 'CMEMS_USERNAME / PASSWORD' },
              { key: 'cds',        label: 'ERA5 Weather (CDS)',    hint: 'CDS_API_KEY' },
              { key: 'earthdata',  label: 'NASA Earthdata',        hint: 'EARTHDATA_USERNAME / PASSWORD' },
              { key: 'llm',        label: `LLM (${status.credentials.llm_provider})`, hint: 'OPENAI/GEMINI/GROQ_API_KEY' },
            ].map(({ key, label, hint }) => {
              const active = !!(status.credentials as any)[key]
              return (
                <div key={key} className={`p-2.5 rounded-lg border text-xs ${active
                  ? 'bg-emerald-950/30 border-emerald-800/30' : 'bg-polar-bg border-polar-border'}`}>
                  <div className={`font-semibold mb-0.5 ${active ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {active ? '✓' : '○'} {label}
                  </div>
                  {!active && <div className="text-slate-600 font-mono">{hint}</div>}
                  {active && <div className="text-emerald-600">Configured</div>}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Sources table */}
      <div className="card overflow-x-auto">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-white">Data Feed Status</div>
          <button
            onClick={() => satRefresh.mutate()}
            disabled={satRefresh.isPending}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${satRefresh.isPending ? 'animate-spin' : ''}`} />
            Refresh Satellite
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 border-b border-polar-border">
              <th className="pb-2.5">Source</th>
              <th className="pb-2.5">Provider</th>
              <th className="pb-2.5">Variables</th>
              <th className="pb-2.5">Resolution</th>
              <th className="pb-2.5">Status</th>
              <th className="pb-2.5">Updated</th>
              <th className="pb-2.5">Records</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-polar-border">
            {sources.map((src) => (
              <tr key={src.source_id} className="hover:bg-polar-border/20 transition-colors">
                <td className="py-2.5 pr-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-white font-medium">{src.source_name}</span>
                    {src.url && src.url !== 'local' && (
                      <a href={src.url.split(' ')[0]} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="w-3 h-3 text-slate-600 hover:text-polar-accent" />
                      </a>
                    )}
                  </div>
                  <div className="text-xs text-slate-600 mt-0.5">{src.source}</div>
                </td>
                <td className="py-2.5 pr-3 text-slate-400 text-xs">
                  {src.credential_required && (
                    <span className={`block font-mono ${src.is_real ? 'text-emerald-600' : 'text-slate-600'}`}>
                      {src.is_real ? '✓ configured' : src.credential_required}
                    </span>
                  )}
                </td>
                <td className="py-2.5 pr-3">
                  <div className="flex flex-wrap gap-1">
                    {(src.variables || []).slice(0, 3).map((v: string) => (
                      <span key={v} className="px-1.5 py-0.5 rounded text-xs bg-polar-bg text-slate-500 border border-polar-border">
                        {v}
                      </span>
                    ))}
                    {(src.variables || []).length > 3 && (
                      <span className="text-xs text-slate-600">+{(src.variables || []).length - 3}</span>
                    )}
                  </div>
                </td>
                <td className="py-2.5 pr-3 text-xs text-slate-500">{src.resolution}</td>
                <td className="py-2.5 pr-3"><StatusBadge status={src.status} /></td>
                <td className="py-2.5 pr-3 text-xs text-slate-500">
                  {src.age_human || (src.last_updated ? new Date(src.last_updated).toLocaleTimeString() : '—')}
                </td>
                <td className="py-2.5 text-xs text-slate-500 font-mono">
                  {src.record_count != null ? src.record_count.toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Disclaimer */}
      <div className="p-4 bg-amber-950/30 border border-amber-800/30 rounded-xl text-sm text-amber-600">
        <div className="font-semibold text-amber-400 mb-1">⚠ Data Disclaimer</div>
        {data?.disclaimer}
        {' '}See <code className="text-amber-400">DATA_SOURCES.md</code> for credential setup instructions.
      </div>
    </div>
  )
}
