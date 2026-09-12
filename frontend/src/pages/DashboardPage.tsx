import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useQueryClient } from '@tanstack/react-query'
import { LayoutDashboard, Snowflake, Mountain, Gauge, Wind, Ship, Activity } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import {
  fetchDashboard, fetchSeaIceCurrent, fetchIcebergs,
  fetchOceanCurrent, fetchSatelliteLatest,
  createVesselsWebSocket, createLiveWebSocket,
} from '../services/api'
import PageHeader      from '../components/PageHeader'
import AntarcticMap    from '../components/AntarcticMap'
import RiskGauge       from '../components/RiskGauge'
import FreshnessTag    from '../components/FreshnessTag'
import LoadingSpinner  from '../components/LoadingSpinner'
import { useActiveVessel, useVesselStore } from '../store/vesselStore'
import type { FreshnessInfo } from '../types'

function StatCard({ icon: Icon, label, value, unit, color = '#0ea5e9', sub, freshness }: {
  icon: any; label: string; value: string | number | null | undefined
  unit?: string; color?: string; sub?: string; freshness?: FreshnessInfo | null
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
          {value ?? '—'}<span className="text-sm font-normal text-slate-400 ml-1">{unit}</span>
        </div>
        {sub && <div className="text-xs text-slate-600">{sub}</div>}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const qc = useQueryClient()
  const activeVessel = useActiveVessel()
  const { updateAllVessels, setActiveVessel, activeVesselMmsi, setActiveVesselMmsi } = useVesselStore()
  const wsRef  = useRef<WebSocket | null>(null)
  const liveWs = useRef<WebSocket | null>(null)

  const { data: dash, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 30_000,
  })
  const { data: seaIce } = useQuery({
    queryKey: ['sea-ice-low'],
    queryFn: () => fetchSeaIceCurrent('low'),
    staleTime: 120_000,
  })
  const { data: icebergsData } = useQuery({
    queryKey: ['icebergs'],
    queryFn: fetchIcebergs,
    staleTime: 60_000,
  })
  const { data: oceanData } = useQuery({
    queryKey: ['ocean-current'],
    queryFn: fetchOceanCurrent,
    staleTime: 120_000,
  })
  const { data: satData } = useQuery({
    queryKey: ['satellite-latest'],
    queryFn: fetchSatelliteLatest,
    staleTime: 300_000,
  })

  // Multi-vessel WebSocket → update vessel store
  useEffect(() => {
    const ws = createVesselsWebSocket((msg) => {
      if (msg.event === 'VESSEL_POSITION_UPDATED' && msg.vessel) {
        updateAllVessels(msg.vessel)
        // If this is the active vessel, update it
        if (msg.mmsi === activeVesselMmsi) {
          setActiveVessel(msg.vessel)
        }
        // If no active vessel selected yet, auto-select first real one
        if (!activeVesselMmsi && msg.vessel?.is_real) {
          setActiveVesselMmsi(msg.vessel.mmsi)
          setActiveVessel(msg.vessel)
        }
      }
      if (msg.event === 'ACTIVE_VESSEL_CHANGED' && msg.vessel) {
        setActiveVessel(msg.vessel)
        setActiveVesselMmsi(msg.mmsi)
      }
      if (msg.event === 'VESSEL_REGISTRY_SNAPSHOT' && msg.vessels?.length) {
        msg.vessels.forEach((v: any) => updateAllVessels(v))
        if (!activeVesselMmsi && msg.vessels[0]?.is_real) {
          setActiveVesselMmsi(msg.vessels[0].mmsi)
          setActiveVessel(msg.vessels[0])
        }
      }
    })
    wsRef.current = ws
    return () => ws.close()
  }, [activeVesselMmsi])

  // /ws/live → invalidate queries on data refresh
  useEffect(() => {
    const ws = createLiveWebSocket((msg) => {
      if (msg.event === 'DATA_REFRESH_COMPLETE') {
        qc.invalidateQueries({ queryKey: ['dashboard'] })
        qc.invalidateQueries({ queryKey: ['icebergs'] })
        qc.invalidateQueries({ queryKey: ['sea-ice-low'] })
        qc.invalidateQueries({ queryKey: ['ocean-current'] })
        qc.invalidateQueries({ queryKey: ['satellite-latest'] })
        qc.invalidateQueries({ queryKey: ['live-status'] })
      }
      if (msg.event === 'SEA_ICE_UPDATED')   qc.invalidateQueries({ queryKey: ['sea-ice-low'] })
      if (msg.event === 'ICEBERGS_UPDATED')  qc.invalidateQueries({ queryKey: ['icebergs'] })
      if (msg.event === 'OCEAN_UPDATED')     qc.invalidateQueries({ queryKey: ['ocean-current'] })
    })
    liveWs.current = ws
    return () => ws.close()
  }, [])

  if (isLoading) return <LoadingSpinner message="Loading Antarctic data..." size="lg" />

  // Prefer active vessel from Zustand store over dashboard API fallback
  const vesselLat  = activeVessel?.latitude  ?? dash?.vessel_lat
  const vesselLon  = activeVessel?.longitude ?? dash?.vessel_lon
  const vesselName = activeVessel?.name      ?? dash?.vessel_name ?? 'No Vessel Selected'
  const isVesselLive = activeVessel?.is_real ?? false
  const vesselDataMode = activeVessel?.data_mode ?? dash?.vessel_data_mode ?? 'offline'

  const systemStatus = dash?.system_status
  const getSrc = (id: string): FreshnessInfo | null =>
    systemStatus?.sources?.find((s: FreshnessInfo) => s.source_id === id) ?? null

  const forecastData = dash?.forecast_accuracy?.map((fa: any) => ({
    horizon: fa.horizon, skill: fa.skill_score != null ? Math.round(fa.skill_score * 100) : null,
  })).filter((d: any) => d.skill != null) || []

  // Vessel for map — only show if real or demo allowed
  const vesselForMap = (vesselLat != null && vesselLon != null) ? {
    mmsi: activeVessel?.mmsi || 'unknown',
    imo: activeVessel?.imo || '',
    vessel_name: vesselName,
    latitude: vesselLat,
    longitude: vesselLon,
    speed_knots: activeVessel?.speed || dash?.vessel_speed_knots || 0,
    heading_deg: activeVessel?.heading || dash?.vessel_heading_deg || 0,
    course_deg: activeVessel?.course || 0,
    navigation_status: activeVessel?.navigation_status || 'unknown',
    timestamp: activeVessel?.timestamp || new Date().toISOString(),
    age_seconds: activeVessel?.age_seconds || 0,
    source: activeVessel?.source || 'unknown',
    is_real: isVesselLive,
    data_mode: vesselDataMode,
    status_label: isVesselLive ? 'LIVE' : 'DEMO',
  } : null

  const riskScore = dash?.current_risk_score ?? 0
  const isDemo = dash?.data_mode === 'demo'

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={LayoutDashboard}
        title="Dashboard"
        subtitle={isDemo ? 'DEMO MODE — Synthetic data' : 'LIVE DATA — Antarctic Navigation Intelligence'}
        showDemoBanner={isDemo}
      />

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={Snowflake} label="Sea Ice Coverage"
          value={dash?.sea_ice_coverage_pct?.toFixed(1)} unit="%"
          color="#67e8f9"
          sub={dash?.sea_ice_extent_km2 ? `${(dash.sea_ice_extent_km2 / 1e6).toFixed(1)}M km²` : undefined}
          freshness={getSrc('sea_ice')}
        />
        <StatCard
          icon={Mountain} label="Active Icebergs"
          value={dash?.active_icebergs} color="#f97316"
          sub={dash?.high_risk_icebergs ? `${dash.high_risk_icebergs} high risk` : undefined}
          freshness={getSrc('icebergs')}
        />
        <StatCard
          icon={Gauge} label="Navigation Risk"
          value={riskScore?.toFixed(0)} unit="/100"
          color={riskScore > 60 ? '#ef4444' : riskScore > 40 ? '#f97316' : '#22c55e'}
          sub={dash?.current_risk_category?.toUpperCase()}
        />
        <StatCard
          icon={Wind} label="Avg Wind Speed"
          value={dash?.avg_wind_speed_ms?.toFixed(1)} unit="m/s"
          color="#a78bfa"
          sub={dash?.avg_sst_celsius != null ? `SST: ${dash.avg_sst_celsius?.toFixed(1)}°C` : undefined}
          freshness={getSrc('weather')}
        />
      </div>

      {/* Map + right panel */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Map */}
        <div className="xl:col-span-2 card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-polar-border">
            <div className="text-sm font-medium text-white">Antarctic Navigation Chart</div>
            <div className="flex items-center gap-3 text-xs">
              {satData?.product && (
                <span className="text-polar-accent">
                  Sentinel-1 · {new Date(satData.product.acquisition_time).toLocaleDateString()}
                </span>
              )}
              <span className={`flex items-center gap-1 ${isVesselLive ? 'text-emerald-400' : vesselDataMode === 'offline' ? 'text-red-400' : 'text-amber-400'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isVesselLive ? 'bg-emerald-400 animate-pulse' : vesselDataMode === 'offline' ? 'bg-red-400' : 'bg-amber-400'}`} />
                {isVesselLive ? `LIVE AIS: ${vesselName}` : vesselDataMode === 'offline' ? 'NO VESSEL' : 'DEMO VESSEL'}
              </span>
            </div>
          </div>
          <AntarcticMap
            seaIceGrid={seaIce?.grid_points ?? []}
            icebergs={icebergsData?.icebergs ?? []}
            vessel={vesselForMap}
            oceanGrid={oceanData?.grid_points ?? []}
            satelliteFootprint={satData?.product?.footprint ?? null}
            layers={{ seaIce: true, icebergs: true, trajectories: false, routes: false,
                      vessel: vesselForMap != null, vesselTrack: false,
                      oceanCurrents: false, satellite: true }}
            height="420px"
          />
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Vessel Status */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <Ship className="w-4 h-4 text-polar-accent" /> Vessel Status
              </div>
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                isVesselLive ? 'bg-emerald-900/50 text-emerald-300 border-emerald-700'
                : vesselDataMode === 'offline' ? 'bg-red-900/30 text-red-400 border-red-800'
                : 'bg-amber-900/50 text-amber-300 border-amber-700'}`}>
                {isVesselLive ? '● LIVE AIS' : vesselDataMode === 'offline' ? '● NO VESSEL' : '● DEMO'}
              </span>
            </div>
            {vesselDataMode === 'offline' && !activeVessel ? (
              <div className="text-xs text-slate-500 text-center py-3">
                No vessel selected.<br />
                <a href="/vessels" className="text-polar-accent hover:underline">Go to Vessels page</a> to select one.
              </div>
            ) : (
              <div className="space-y-1.5 text-sm">
                {[
                  ['Name',     vesselName],
                  ['MMSI',     activeVessel?.mmsi ?? dash?.vessel_mmsi ?? '—'],
                  ['Position', vesselLat != null ? `${vesselLat.toFixed(4)}°, ${vesselLon?.toFixed(4)}°` : 'Unknown'],
                  ['Speed',    `${(activeVessel?.speed || dash?.vessel_speed_knots || 0).toFixed(1)} kts`],
                  ['Heading',  `${(activeVessel?.heading || dash?.vessel_heading_deg || 0).toFixed(0)}°`],
                  ['Status',   activeVessel?.navigation_status || dash?.vessel_status || '—'],
                  ['Last Upd', activeVessel?.age_seconds != null
                    ? (activeVessel.age_seconds < 60 ? `${activeVessel.age_seconds.toFixed(0)}s ago` : `${(activeVessel.age_seconds/60).toFixed(0)}m ago`)
                    : '—'],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-500">{k}</span>
                    <span className="text-white text-xs font-mono truncate max-w-[140px]">{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Navigation Risk */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-polar-accent" /> Navigation Risk
            </div>
            <RiskGauge score={riskScore} label="Overall" size="md" />
            <div className="grid grid-cols-2 gap-3 pt-3">
              {[
                { label: 'Sea Ice',  value: dash?.sea_ice_risk ?? 0, color: '#67e8f9' },
                { label: 'Iceberg', value: dash?.iceberg_risk ?? 0,  color: '#f97316' },
                { label: 'Weather', value: dash?.weather_risk ?? 0,  color: '#a78bfa' },
                { label: 'Ocean',   value: dash?.ocean_risk ?? 0,    color: '#0ea5e9' },
              ].map(item => (
                <div key={item.label} className="space-y-1">
                  <div className="text-xs text-slate-500">{item.label}</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-polar-border rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${item.value}%`, background: item.color }} />
                    </div>
                    <span className="text-xs font-mono" style={{ color: item.color }}>
                      {item.value.toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Forecast accuracy (only if real data) */}
          {forecastData.length > 0 && (
            <div className="card">
              <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-polar-accent" /> Model Skill Score
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <AreaChart data={forecastData}>
                  <defs>
                    <linearGradient id="skillG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
                  <XAxis dataKey="horizon" tick={{ fill: '#64748b', fontSize: 9 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 9 }} unit="%" />
                  <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 6 }}
                           formatter={(v: any) => [`${v}%`]} />
                  <Area type="monotone" dataKey="skill" stroke="#0ea5e9" fill="url(#skillG)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
