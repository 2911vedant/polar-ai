import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Snowflake, TrendingUp, Clock } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from 'recharts'
import { fetchSeaIceCurrent, fetchSeaIceHistory, fetchSeaIceForecast } from '../services/api'
import PageHeader from '../components/PageHeader'
import AntarcticMap from '../components/AntarcticMap'
import LoadingSpinner from '../components/LoadingSpinner'

const HORIZONS = [24, 48, 72, 168]

export default function SeaIcePage() {
  const [selectedHorizon, setSelectedHorizon] = useState(72)
  const [resolution, setResolution] = useState<'low' | 'medium'>('low')
  const [historyDays, setHistoryDays] = useState(90)

  const { data: current, isLoading: currentLoading } = useQuery({
    queryKey: ['sea-ice-current', resolution],
    queryFn: () => fetchSeaIceCurrent(resolution),
    staleTime: 60_000,
  })
  const { data: history } = useQuery({
    queryKey: ['sea-ice-history', historyDays],
    queryFn: () => fetchSeaIceHistory(historyDays),
    staleTime: 120_000,
  })
  const { data: forecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['sea-ice-forecast', selectedHorizon],
    queryFn: () => fetchSeaIceForecast(selectedHorizon),
    staleTime: 120_000,
  })

  const histData = history?.data_points?.map((d: any) => ({
    date: d.date.slice(5, 10),
    coverage: d.coverage_pct,
    extent: d.extent_km2 / 1_000_000,
  })) || []

  // Map forecast grid as pseudo-SIC data
  const forecastGridPoints = forecast?.grid_points?.map((gp: any) => ({
    latitude: gp.latitude,
    longitude: gp.longitude,
    concentration: gp.predicted_concentration,
    ice_category: gp.risk_category === 'consolidated' ? 'consolidated' :
                  gp.predicted_concentration > 0.65 ? 'high' :
                  gp.predicted_concentration > 0.40 ? 'moderate' :
                  gp.predicted_concentration > 0.15 ? 'low' : 'open_water',
  })) || []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Snowflake}
        title="Sea Ice Forecast"
        subtitle="Antarctic sea-ice concentration monitoring and prediction"
        actions={
          <div className="flex items-center gap-2">
            <select
              value={resolution}
              onChange={e => setResolution(e.target.value as any)}
              className="input-field w-32"
            >
              <option value="low">Low Res</option>
              <option value="medium">Medium Res</option>
            </select>
          </div>
        }
      />

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Coverage', value: `${current?.coverage_pct?.toFixed(1) || '--'}%`, sub: 'of monitored region' },
          { label: 'Extent', value: `${((current?.extent_km2 || 0) / 1e6).toFixed(1)}M`, sub: 'km²' },
          { label: 'Model Confidence', value: `${((forecast?.overall_confidence || 0) * 100).toFixed(0)}%`, sub: `at ${selectedHorizon}h horizon` },
          { label: 'MAE', value: forecast?.mae?.toFixed(3) || '--', sub: 'mean absolute error' },
        ].map(s => (
          <div key={s.label} className="card">
            <div className="text-xs text-slate-500">{s.label}</div>
            <div className="text-2xl font-bold text-white">{s.value}</div>
            <div className="text-xs text-slate-600">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Forecast horizon selector */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-polar-accent" />
            Forecast Horizon
          </div>
          <div className="flex gap-1">
            {HORIZONS.map(h => (
              <button
                key={h}
                onClick={() => setSelectedHorizon(h)}
                className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                  selectedHorizon === h
                    ? 'bg-polar-accent text-white'
                    : 'bg-polar-border text-slate-400 hover:text-white'
                }`}
              >
                {h < 24 ? `${h}h` : h < 168 ? `${h/24}d` : '7d'}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {/* Current map */}
          <div>
            <div className="text-xs text-slate-500 mb-2">Current Conditions</div>
            {currentLoading ? <LoadingSpinner /> : (
              <AntarcticMap
                seaIceGrid={current?.grid_points || []}
                //
                //
                //
                height="320px"
              />
            )}
          </div>
          {/* Forecast map */}
          <div>
            <div className="text-xs text-slate-500 mb-2">
              Forecast: +{selectedHorizon}h
              {forecast && (
                <span className="ml-2 text-polar-accent">
                  Confidence: {((forecast.overall_confidence || 0) * 100).toFixed(0)}%
                </span>
              )}
            </div>
            {forecastLoading ? <LoadingSpinner /> : (
              <AntarcticMap
                seaIceGrid={forecastGridPoints}
                //
                //
                //
                height="320px"
              />
            )}
          </div>
        </div>
      </div>

      {/* Historical chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-semibold text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-polar-accent" />
            Historical Sea Ice Coverage
          </div>
          <div className="flex gap-1">
            {[30, 90, 180, 365].map(d => (
              <button
                key={d}
                onClick={() => setHistoryDays(d)}
                className={`px-2 py-1 rounded text-xs transition-colors ${
                  historyDays === d ? 'bg-polar-accent text-white' : 'bg-polar-border text-slate-400 hover:text-white'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={histData}>
            <defs>
              <linearGradient id="iceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#67e8f9" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#67e8f9" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval={Math.floor(histData.length / 8)} />
            <YAxis domain={[20, 75]} tick={{ fill: '#64748b', fontSize: 10 }} unit="%" />
            <Tooltip
              contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }}
              labelStyle={{ color: '#94a3b8' }}
              itemStyle={{ color: '#67e8f9' }}
            />
            <Area type="monotone" dataKey="coverage" stroke="#67e8f9" fill="url(#iceGrad)" strokeWidth={2} name="Coverage %" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="card">
        <div className="text-xs text-slate-500 mb-2">Sea Ice Concentration Legend</div>
        <div className="flex flex-wrap gap-3">
          {[
            { label: 'Open Water (< 15%)', color: '#1e3a5f' },
            { label: 'Low Ice (15–40%)', color: '#3b82f6' },
            { label: 'Moderate (40–65%)', color: '#93c5fd' },
            { label: 'High Ice (65–85%)', color: '#e2e8f0' },
            { label: 'Consolidated (> 85%)', color: '#f8fafc' },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-1.5 text-xs text-slate-400">
              <div className="w-4 h-3 rounded-sm border border-slate-700" style={{ background: item.color }} />
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
