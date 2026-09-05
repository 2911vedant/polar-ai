import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Navigation, Fuel, Shield, Zap, Scale, AlertTriangle, CheckCircle } from 'lucide-react'
import { compareRoutes } from '../services/api'
import PageHeader from '../components/PageHeader'
import AntarcticMap from '../components/AntarcticMap'
import LoadingSpinner from '../components/LoadingSpinner'
import { getRiskBadgeClass } from '../utils/risk'
import type { Route } from '../types'

const STATIONS = [
  { name: 'McMurdo Station', lat: -77.85, lon: 166.67 },
  { name: 'Palmer Station', lat: -64.77, lon: -64.05 },
  { name: 'Rothera Station', lat: -67.57, lon: -68.13 },
  { name: 'Mawson Station', lat: -67.60, lon: 62.87 },
  { name: 'Casey Station', lat: -66.28, lon: 110.52 },
  { name: 'Halley Station', lat: -75.52, lon: -26.57 },
  { name: 'Vessel Position', lat: -66.0, lon: -60.0 },
]

const ROUTE_ICONS: Record<string, any> = {
  shortest: Zap,
  safest: Shield,
  fuel_efficient: Fuel,
  balanced: Scale,
}

const ROUTE_COLORS: Record<string, string> = {
  shortest: '#f59e0b',
  safest: '#22c55e',
  fuel_efficient: '#0ea5e9',
  balanced: '#a855f7',
}

function RouteCard({ route, isSelected, isRecommended, onClick }: {
  route: Route; isSelected: boolean; isRecommended: boolean; onClick: () => void
}) {
  const Icon = ROUTE_ICONS[route.route_type] || Navigation
  const color = ROUTE_COLORS[route.route_type] || '#94a3b8'
  const riskPct = (route.overall_risk_score * 100).toFixed(0)

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 rounded-xl border transition-all ${
        isSelected
          ? 'border-2 bg-polar-card'
          : 'border border-polar-border bg-polar-card hover:border-slate-500'
      }`}
      style={isSelected ? { borderColor: color } : {}}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: color + '20' }}>
            <Icon className="w-4 h-4" style={{ color }} />
          </div>
          <div>
            <div className="text-sm font-semibold text-white capitalize">
              {route.route_type.replace('_', ' ')}
            </div>
            {isRecommended && (
              <div className="flex items-center gap-1 text-xs text-emerald-400">
                <CheckCircle className="w-3 h-3" /> Recommended
              </div>
            )}
          </div>
        </div>
        <span className={getRiskBadgeClass(route.risk_category)}>
          {riskPct}/100
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-slate-500">Distance</div>
          <div className="text-white font-mono">{route.total_distance_km.toFixed(0)} km</div>
        </div>
        <div>
          <div className="text-slate-500">ETA</div>
          <div className="text-white font-mono">{route.estimated_duration_hours.toFixed(0)}h</div>
        </div>
        <div>
          <div className="text-slate-500">Fuel</div>
          <div className="text-white font-mono">{route.estimated_fuel_tonnes.toFixed(0)} t</div>
        </div>
        <div>
          <div className="text-slate-500">Avg Ice</div>
          <div className="text-white font-mono">{(route.avg_ice_concentration * 100).toFixed(0)}%</div>
        </div>
      </div>
      {route.iceberg_intersections > 0 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-amber-400">
          <AlertTriangle className="w-3 h-3" />
          {route.iceberg_intersections} iceberg zone(s)
        </div>
      )}
    </button>
  )
}

export default function RoutePlannerPage() {
  const [originIdx, setOriginIdx] = useState(6)  // Vessel Position
  const [destIdx, setDestIdx] = useState(2)      // Rothera
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [comparison, setComparison] = useState<any>(null)

  const mutation = useMutation({
    mutationFn: compareRoutes,
    onSuccess: (data) => {
      setComparison(data)
      if (data.routes?.length > 0) {
        const rec = data.routes.find((r: Route) => r.route_type === data.recommended_route_type)
        setSelectedRouteId(rec?.id || data.routes[0].id)
      }
    },
  })

  const origin = STATIONS[originIdx]
  const dest = STATIONS[destIdx]
  const selectedRoute = comparison?.routes?.find((r: Route) => r.id === selectedRouteId) || null

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Navigation}
        title="Route Planner"
        subtitle="AI-powered Antarctic navigation route optimization"
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: inputs + route cards */}
        <div className="space-y-4">
          {/* Input form */}
          <div className="card space-y-3">
            <div className="text-sm font-semibold text-white">Route Parameters</div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Origin</label>
              <select
                value={originIdx}
                onChange={e => setOriginIdx(Number(e.target.value))}
                className="input-field"
              >
                {STATIONS.map((s, i) => (
                  <option key={s.name} value={i}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Destination</label>
              <select
                value={destIdx}
                onChange={e => setDestIdx(Number(e.target.value))}
                className="input-field"
              >
                {STATIONS.map((s, i) => (
                  <option key={s.name} value={i}>{s.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => mutation.mutate({
                origin_lat: origin.lat,
                origin_lon: origin.lon,
                origin_name: origin.name,
                destination_lat: dest.lat,
                destination_lon: dest.lon,
                destination_name: dest.name,
              })}
              disabled={mutation.isPending || originIdx === destIdx}
              className="btn-primary w-full"
            >
              {mutation.isPending ? 'Computing Routes...' : 'Generate All Routes'}
            </button>
          </div>

          {/* Route cards */}
          {mutation.isPending && <LoadingSpinner message="Running A* routing..." />}
          {comparison?.routes && (
            <div className="space-y-2">
              <div className="text-xs text-slate-500">Select a route to view on map</div>
              {comparison.routes.map((route: Route) => (
                <RouteCard
                  key={route.id}
                  route={route}
                  isSelected={selectedRouteId === route.id}
                  isRecommended={route.route_type === comparison.recommended_route_type}
                  onClick={() => setSelectedRouteId(route.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: Map + route detail */}
        <div className="xl:col-span-2 space-y-4">
          <AntarcticMap
            routes={comparison?.routes || []}
            selectedRoute={selectedRoute}
            //
            //
            //
            //
            //
            //
            height="400px"
          />

          {/* Route comparison table */}
          {comparison?.routes && (
            <div className="card overflow-x-auto">
              <div className="text-sm font-semibold text-white mb-3">Route Comparison</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-polar-border">
                    <th className="text-left pb-2">Route</th>
                    <th className="text-right pb-2">Distance</th>
                    <th className="text-right pb-2">ETA</th>
                    <th className="text-right pb-2">Fuel</th>
                    <th className="text-right pb-2">Risk</th>
                    <th className="text-right pb-2">Ice</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-polar-border">
                  {comparison.routes.map((r: Route) => {
                    const color = ROUTE_COLORS[r.route_type]
                    const isRec = r.route_type === comparison.recommended_route_type
                    return (
                      <tr
                        key={r.id}
                        className={`cursor-pointer transition-colors ${selectedRouteId === r.id ? 'bg-polar-border/50' : 'hover:bg-polar-border/30'}`}
                        onClick={() => setSelectedRouteId(r.id)}
                      >
                        <td className="py-2 pr-2">
                          <div className="flex items-center gap-1.5">
                            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                            <span className="text-white capitalize">{r.route_type.replace('_', ' ')}</span>
                            {isRec && <span className="text-emerald-400">★</span>}
                          </div>
                        </td>
                        <td className="py-2 text-right text-white font-mono">{r.total_distance_km.toFixed(0)} km</td>
                        <td className="py-2 text-right text-white font-mono">{r.estimated_duration_hours.toFixed(0)}h</td>
                        <td className="py-2 text-right text-white font-mono">{r.estimated_fuel_tonnes.toFixed(0)} t</td>
                        <td className="py-2 text-right">
                          <span className={getRiskBadgeClass(r.risk_category)}>
                            {(r.overall_risk_score * 100).toFixed(0)}
                          </span>
                        </td>
                        <td className="py-2 text-right text-white font-mono">{(r.avg_ice_concentration * 100).toFixed(0)}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {comparison.recommendation_reason && (
                <div className="mt-3 p-3 bg-emerald-950/30 border border-emerald-800/30 rounded-lg text-xs text-emerald-400">
                  <div className="font-semibold mb-1">★ AI Recommendation</div>
                  {comparison.recommendation_reason}
                </div>
              )}
            </div>
          )}

          {/* Selected route details */}
          {selectedRoute && (
            <div className="card">
              <div className="text-sm font-semibold text-white mb-3">
                Route Details — {selectedRoute.route_type.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
              </div>
              <div className="space-y-1">
                {selectedRoute.risk_factors.slice(0, 4).map((f: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-400">
                    <span className="text-slate-600 mt-0.5">•</span>
                    {f}
                  </div>
                ))}
              </div>
              {selectedRoute.recommendations.length > 0 && (
                <div className="mt-3 space-y-1">
                  <div className="text-xs text-slate-500">Recommendations</div>
                  {selectedRoute.recommendations.map((r: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-emerald-400">
                      <span>→</span>
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
