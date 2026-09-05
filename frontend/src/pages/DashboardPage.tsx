import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LayoutDashboard, Snowflake, Mountain, Gauge, Wind, Navigation, Satellite } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import {
  fetchDashboard, fetchSeaIceCurrent, fetchIcebergs,
  fetchVesselPosition, fetchVesselTrack, fetchOceanCurrent,
  fetchSatelliteLatest, createVesselWebSocket,
} from '../services/api'
import PageHeader     from '../components/PageHeader'
import AntarcticMap   from '../components/AntarcticMap'
import RiskGauge      from '../components/RiskGauge'
import FreshnessTag   from '../components/FreshnessTag'
import LoadingSpinner from '../components/LoadingSpinner'
import type { VesselPosition, FreshnessInfo } from '../types'

function StatCard({ icon: Icon, label, value, unit, color = '#0ea5e9', sub, freshness }: {
  icon: any; label: string; value: string | number; unit?: string
  color?: string; sub?: string; freshness?: FreshnessInfo | null
}) {
  return (
    <div className="card flex items-start gap-3">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
           style={{ background: color + '20', border: `1px solid ${color}40` }}>
        <Icon className="w-4 h-4" style={{ color }} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-slate-500 truncate">{label}</div>
          {freshness && <FreshnessTag freshness={freshness} compact />}
        </div>
        <div className="text-xl font-bold text-white">
          {value}<span className="text-sm font-normal text-slate-400 ml-1">{unit}</span>
        </div>
        {sub && <div className="text-xs text-slate-600">{sub}</div>}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [liveVessel, setLiveVessel] = useState<VesselPosition | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const { data: dash, isLoading } = useQuery({
    queryKey: ['dashboard'], queryFn: fetchDashboard, refetchInterval: 30_000,
  })
  const { data: seaIce } = useQuery({
    queryKey: ['sea-ice-low'], queryFn: () => fetchSeaIceCurrent('low'), staleTime: 120_000,
  })
  const { data: icebergsData } = useQuery({
    queryKey: ['icebergs'], queryFn: fetchIcebergs, staleTime: 60_000,
  })
  const { data: vesselData } = useQuery({
    queryKey: ['vessel-position'], queryFn: fetchVesselPosition, refetchInterval: 10_000,
  })
  const { data: trackData } = useQuery({
    queryKey: ['vessel-track-1h'], queryFn: () => fetchVesselTrack(1), staleTime: 30_000,
  })
  const { data: oceanData } = useQuery({
    queryKey: ['ocean-current'], queryFn: fetchOceanCurrent, staleTime: 120_000,
  })
  const { data: satData } = useQuery({
    queryKey: ['satellite-latest'], queryFn: fetchSatelliteLatest, staleTime: 300_000,
  })

  // WebSocket for live vessel updates
  useEffect(() => {
    const ws = createVesselWebSocket((msg) => {
      if (msg.type === 'vessel_position' && msg.position) {
        setLiveVessel(msg.position)
      }
    })
    wsRef.current = ws
    return () => { ws.close() }
  }, [])

  if (isLoading) return <LoadingSpinner message="Loading Antarctic data..." size="lg" />

  const vessel: VesselPosition | null = liveVessel || vesselData?.position || null
  const vesselLat = vessel?.latitude ?? dash?.vessel_lat ?? -66.0
  const vesselLon = vessel?.longitude ?? dash?.vessel_lon ?? -60.0
  const isVesselLive = vessel?.is_real ?? false

  const systemStatus = dash?.system_status
  const getSrc = (id: string): FreshnessInfo | null =>
    systemStatus?.sources?.find((s: FreshnessInfo) => s.source_id === id) ?? null

  const forecastData = dash?.forecast_accuracy?.map((fa: any) => ({
    horizon: fa.horizon, skill: Math.round(fa.skill_score * 100),
  })) || []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader icon={LayoutDashboard} title="Dashboard"
        subtitle="Antarctic Navigation Intelligence — real-time overview" />

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Snowflake} label="Sea Ice Coverage"
          value={dash?.sea_ice_coverage_pct?.toFixed(1) ?? '--'} unit="%"
          color="#67e8f9"
          sub={`${((dash?.sea_ice_extent_km2 ?? 0) / 1e6).toFixed(1)}M km²`}
          freshness={getSrc('sea_ice')} />
        <StatCard icon={Mountain} label="Active Icebergs"
          value={dash?.active_icebergs ?? '--'}
          color="#f97316"
          sub={`${dash?.high_risk_icebergs ?? 0} high risk`}
          freshness={getSrc('icebergs')} />
        <StatCard icon={Gauge} label="Navigation Risk"
          value={dash?.current_risk_score?.toFixed(0) ?? '--'} unit="/100"
          color={dash?.current_risk_score > 60 ? '#ef4444' : dash?.current_risk_score > 40 ? '#f97316' : '#22c55e'}
          sub={dash?.current_risk_category?.toUpperCase()} />
        <StatCard icon={Wind} label="Avg Wind Speed"
          value={dash?.avg_wind_speed_ms?.toFixed(1) ?? '--'} unit="m/s"
          color="#a78bfa"
          sub={dash?.avg_sst_celsius ? `SST ${dash.avg_sst_celsius?.toFixed(1)}°C` : 'Wind data'}
          freshness={getSrc('weather')} />
      </div>

      {/* Main: map + right panel */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Map */}
        <div className="xl:col-span-2 card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-polar-border">
            <div className="text-sm font-medium text-white flex items-center gap-2">
              <Satellite className="w-4 h-4 text-polar-accent" />
              Antarctic Navigation Chart
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              {satData?.product && (
                <span className="text-polar-accent">
                  Sentinel-1 · {new Date(satData.product.acquisition_time).toLocaleDateString()}
                </span>
              )}
              <span className={`flex items-center gap-1 ${isVesselLive ? 'text-emerald-400' : 'text-amber-400'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isVesselLive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                Vessel {isVesselLive ? 'LIVE' : 'DEMO'}
              </span>
            </div>
          </div>
          <AntarcticMap
            seaIceGrid={seaIce?.grid_points ?? []}
            icebergs={icebergsData?.icebergs ?? []}
            vessel={vessel}
            vesselTrack={trackData?.track ?? []}
            oceanGrid={oceanData?.grid_points ?? []}
            satelliteFootprint={satData?.product?.footprint ?? null}
            layers={{ seaIce: true, icebergs: true, trajectories: false, routes: false,
                      vessel: true, vesselTrack: true, oceanCurrents: false, satellite: true }}
            height="420px"
          />
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Vessel status */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold text-white">Vessel Status</div>
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${isVesselLive
                ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700' 
                : 'bg-amber-900/50 text-amber-300 border border-amber-700'}`}>
                {isVesselLive ? '● LIVE AIS' : '● DEMO'}
              </span>
            </div>
            <div className="space-y-1.5 text-sm">
              {[
                ['Name', vessel?.vessel_name ?? 'RV Polar Explorer'],
                ['Position', `${vesselLat.toFixed(4)}°S, ${vesselLon.toFixed(4)}°`],
                ['Speed', `${vessel?.speed_knots?.toFixed(1) ?? '11.5'} kts`],
                ['Heading', `${vessel?.heading_deg?.toFixed(0) ?? '145'}°`],
                ['Status', vessel?.navigation_status ?? 'underway'],
                ['Last Update', vessel?.age_seconds != null
                  ? (vessel.age_seconds < 60 ? `${vessel.age_seconds.toFixed(0)}s ago` : `${(vessel.age_seconds / 60).toFixed(0)}m ago`)
                  : '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-slate-500">{k}</span>
                  <span className="text-white text-xs font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation Risk */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-polar-accent" />Navigation Risk
            </div>
            <RiskGauge score={dash?.current_risk_score ?? 0} label="Overall" size="md" />
            <div className="grid grid-cols-2 gap-3 pt-3">
              {[
                { label: 'Sea Ice',  value: dash?.sea_ice_risk ?? 0,  color: '#67e8f9' },
                { label: 'Iceberg', value: dash?.iceberg_risk ?? 0,   color: '#f97316' },
                { label: 'Weather', value: dash?.weather_risk ?? 0,   color: '#a78bfa' },
                { label: 'Ocean',   value: dash?.ocean_risk ?? 0,     color: '#0ea5e9' },
              ].map(item => (
                <div key={item.label} className="space-y-1">
                  <div className="text-xs text-slate-500">{item.label}</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-polar-border rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${item.value}%`, background: item.color }} />
                    </div>
                    <span className="text-xs font-mono" style={{ color: item.color }}>{item.value.toFixed(0)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Model accuracy */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3">Forecast Skill Score</div>
            <ResponsiveContainer width="100%" height={90}>
              <AreaChart data={forecastData}>
                <defs>
                  <linearGradient id="skillGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#0ea5e9" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
                <XAxis dataKey="horizon" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} unit="%" />
                <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 6 }}
                         itemStyle={{ color: '#0ea5e9' }} formatter={(v: any) => [`${v}%`]} />
                <Area type="monotone" dataKey="skill" stroke="#0ea5e9" fill="url(#skillGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
