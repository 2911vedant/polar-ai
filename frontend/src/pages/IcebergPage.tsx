import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Mountain, Navigation, AlertTriangle } from 'lucide-react'
import { fetchIcebergs, fetchIcebergDetail, fetchIcebergTrajectory } from '../services/api'
import PageHeader from '../components/PageHeader'
import AntarcticMap from '../components/AntarcticMap'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Iceberg, IcebergTrajectory, TrajectoryPoint } from '../types'
import { getRiskBadgeClass } from '../utils/risk'

function IcebergCard({ iceberg, isSelected, onClick }: {
  iceberg: Iceberg; isSelected: boolean; onClick: () => void
}) {
  const riskClass = getRiskBadgeClass(iceberg.risk_level)
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg border transition-all ${
        isSelected
          ? 'bg-polar-accent/10 border-polar-accent/40'
          : 'bg-polar-card border-polar-border hover:border-polar-accent/30'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-white text-sm">{iceberg.iceberg_name}</div>
        <span className={riskClass}>{iceberg.risk_level}</span>
      </div>
      <div className="mt-1 text-xs text-slate-500 space-y-0.5">
        <div>{iceberg.length_km?.toFixed(0)} × {iceberg.width_km?.toFixed(0)} km</div>
        <div className="font-mono">{iceberg.latitude?.toFixed(2)}°S, {iceberg.longitude?.toFixed(2)}°</div>
      </div>
    </button>
  )
}

export default function IcebergPage() {
  const [selectedName, setSelectedName] = useState<string | null>(null)

  const { data: icebergsData, isLoading } = useQuery({
    queryKey: ['icebergs'],
    queryFn: fetchIcebergs,
    staleTime: 60_000,
  })
  const { data: detailData } = useQuery({
    queryKey: ['iceberg-detail', selectedName],
    queryFn: () => fetchIcebergDetail(selectedName!),
    enabled: !!selectedName,
    staleTime: 60_000,
  })
  const { data: trajectoryData } = useQuery({
    queryKey: ['iceberg-trajectory', selectedName],
    queryFn: () => fetchIcebergTrajectory(selectedName!, 72),
    enabled: !!selectedName,
    staleTime: 60_000,
  })

  const icebergs: Iceberg[] = icebergsData?.icebergs || []
  const selectedIceberg = icebergs.find(ib => ib.iceberg_name === selectedName)

  const trajectoryMap = new Map<string, TrajectoryPoint[]>()
  if (trajectoryData?.trajectory && selectedName) {
    trajectoryMap.set(selectedName, trajectoryData.trajectory)
  }

  if (isLoading) return <LoadingSpinner message="Loading iceberg data..." size="lg" />

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Mountain}
        title="Iceberg Intelligence"
        subtitle="Antarctic iceberg tracking and trajectory prediction"
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Iceberg list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-slate-300">
              {icebergs.length} Active Icebergs
            </div>
            <div className="flex items-center gap-1 text-xs text-amber-400">
              <AlertTriangle className="w-3 h-3" />
              {icebergsData?.high_risk_count || 0} High Risk
            </div>
          </div>
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {icebergs.map(ib => (
              <IcebergCard
                key={ib.iceberg_name}
                iceberg={ib}
                isSelected={selectedName === ib.iceberg_name}
                onClick={() => setSelectedName(
                  selectedName === ib.iceberg_name ? null : ib.iceberg_name
                )}
              />
            ))}
          </div>
        </div>

        {/* Map */}
        <div className="xl:col-span-2 space-y-4">
          <AntarcticMap
            icebergs={icebergs}
            trajectories={trajectoryMap}
            vessel={null}
            layers={{ seaIce: false, icebergs: true, trajectories: true, routes: false, vessel: true }}
            height="380px"
            onIcebergClick={(ib) => setSelectedName(ib.iceberg_name)}
          />

          {/* Selected iceberg detail */}
          {selectedName && detailData && (
            <div className="card space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-base font-bold text-white">{detailData.iceberg_name}</div>
                <span className={getRiskBadgeClass(detailData.risk_level)}>
                  {detailData.risk_level.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Length', value: `${detailData.length_km?.toFixed(0)} km` },
                  { label: 'Width', value: `${detailData.width_km?.toFixed(0)} km` },
                  { label: 'Area', value: `${detailData.area_km2?.toFixed(0)} km²` },
                  { label: 'Speed', value: `${detailData.drift_speed_kmh?.toFixed(2)} km/h` },
                  { label: 'Direction', value: `${detailData.drift_direction_deg?.toFixed(0)}°` },
                  { label: 'Latitude', value: `${detailData.latitude?.toFixed(4)}°S` },
                  { label: 'Longitude', value: `${detailData.longitude?.toFixed(4)}°` },
                  { label: 'Status', value: detailData.status },
                ].map(f => (
                  <div key={f.label}>
                    <div className="text-xs text-slate-500">{f.label}</div>
                    <div className="text-sm text-white font-mono">{f.value}</div>
                  </div>
                ))}
              </div>

              {trajectoryData && (
                <div>
                  <div className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                    <Navigation className="w-4 h-4 text-polar-accent" />
                    Predicted Trajectory
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {trajectoryData.trajectory.map((tp: any) => (
                      <div key={tp.horizon_hours} className="card bg-polar-bg py-2 px-3 text-xs">
                        <div className="text-slate-500">+{tp.horizon_hours}h</div>
                        <div className="text-white font-mono">{tp.latitude.toFixed(3)}°</div>
                        <div className="text-white font-mono">{tp.longitude.toFixed(3)}°</div>
                        <div className="text-polar-accent">{(tp.confidence * 100).toFixed(0)}% conf</div>
                      </div>
                    ))}
                  </div>
                  {trajectoryData.closest_approach_km && (
                    <div className="mt-2 flex items-center gap-2 text-xs">
                      <AlertTriangle className="w-3 h-3 text-amber-400" />
                      <span className="text-amber-400">
                        Closest approach to vessel: {trajectoryData.closest_approach_km.toFixed(0)} km
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
