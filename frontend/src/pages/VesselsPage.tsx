/**
 * POLAR-AI Vessels Page
 * Live vessel search, selection, tracking, and hazard analysis.
 */
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Ship, Search, MapPin, Navigation, AlertTriangle, Clock,
         ChevronRight, Anchor, Activity, RefreshCw } from 'lucide-react'
import { searchVessels, fetchActiveVessel, selectVessel,
         fetchVesselTrack, fetchVesselHazards, createVesselsWebSocket } from '../services/api'
import PageHeader from '../components/PageHeader'
import AntarcticMap from '../components/AntarcticMap'
import FreshnessTag from '../components/FreshnessTag'
import LoadingSpinner from '../components/LoadingSpinner'
import { useVesselStore } from '../store/vesselStore'
import type { VesselSummary } from '../store/vesselStore'
import type { FreshnessInfo } from '../types'
import { getRiskBadgeClass } from '../utils/risk'

function VesselCard({ vessel, isActive, onSelect }: {
  vessel: VesselSummary; isActive: boolean; onSelect: () => void
}) {
  const ageS = vessel.age_seconds || 0
  const ageStr = ageS < 60 ? `${Math.round(ageS)}s ago`
    : ageS < 3600 ? `${Math.round(ageS / 60)}m ago`
    : `${Math.round(ageS / 3600)}h ago`

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border transition-all ${
        isActive
          ? 'bg-polar-accent/10 border-polar-accent/50'
          : 'bg-polar-card border-polar-border hover:border-slate-500'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <Ship className="w-3.5 h-3.5 text-polar-accent flex-shrink-0" />
          <span className="text-white text-sm font-medium truncate">
            {vessel.name || vessel.mmsi}
          </span>
        </div>
        <span className={`text-xs font-bold flex-shrink-0 ${
          vessel.is_real ? 'text-emerald-400' : 'text-amber-400'
        }`}>
          {vessel.status_label}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 text-xs text-slate-500 mt-1">
        <span>MMSI: {vessel.mmsi}</span>
        {vessel.imo && <span>IMO: {vessel.imo}</span>}
        {vessel.latitude != null && (
          <>
            <span>{vessel.latitude.toFixed(3)}°</span>
            <span>{vessel.longitude?.toFixed(3)}°</span>
          </>
        )}
        <span>{vessel.speed?.toFixed(1)} kts</span>
        <span className="text-slate-600">{ageStr}</span>
      </div>
      {vessel.ship_type_name && (
        <div className="mt-1 text-xs text-slate-600">{vessel.ship_type_name}</div>
      )}
    </button>
  )
}

function VesselDetailPanel({ vessel, freshness }: {
  vessel: VesselSummary; freshness?: FreshnessInfo | null
}) {
  const [trackHours, setTrackHours] = useState(6)
  const qc = useQueryClient()

  const { data: track } = useQuery({
    queryKey: ['vessel-track', vessel.mmsi, trackHours],
    queryFn: () => fetchVesselTrack(vessel.mmsi, trackHours),
    staleTime: 30_000,
    enabled: !!vessel.mmsi,
  })

  const { data: hazards } = useQuery({
    queryKey: ['vessel-hazards', vessel.mmsi],
    queryFn: () => fetchVesselHazards(vessel.mmsi, 200),
    staleTime: 60_000,
    enabled: !!vessel.mmsi,
  })

  const fields = [
    ['Name',       vessel.name || '—'],
    ['MMSI',       vessel.mmsi],
    ['IMO',        vessel.imo || '—'],
    ['Call Sign',  vessel.call_sign || '—'],
    ['Type',       vessel.ship_type_name || '—'],
    ['Flag',       vessel.flag || '—'],
    ['Status',     vessel.navigation_status || '—'],
    ['Speed',      vessel.speed != null ? `${vessel.speed.toFixed(1)} kts` : '—'],
    ['Course',     vessel.course != null ? `${vessel.course.toFixed(0)}°` : '—'],
    ['Heading',    vessel.heading != null ? `${vessel.heading.toFixed(0)}°` : '—'],
    ['Destination',vessel.destination || '—'],
    ['ETA',        vessel.eta || '—'],
  ]

  const trackCoords = track?.track || []
  const nearestIceberg = hazards?.nearest_iceberg
  const localIce = hazards?.local_sea_ice

  return (
    <div className="space-y-4">
      {/* Freshness */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-white">Vessel Detail</span>
        <FreshnessTag freshness={freshness} compact />
      </div>

      {/* Position */}
      {vessel.latitude != null && (
        <div className="card bg-polar-bg">
          <div className="text-xs text-slate-500 mb-2">Current Position</div>
          <div className="font-mono text-sm text-white">
            {vessel.latitude.toFixed(5)}°S, {vessel.longitude?.toFixed(5)}°
          </div>
        </div>
      )}

      {/* Fields */}
      <div className="grid grid-cols-2 gap-1.5 text-xs">
        {fields.map(([label, value]) => (
          <div key={label} className="bg-polar-bg rounded p-2">
            <div className="text-slate-600 mb-0.5">{label}</div>
            <div className="text-white font-mono truncate">{value}</div>
          </div>
        ))}
      </div>

      {/* Track selector */}
      <div>
        <div className="text-xs text-slate-500 mb-1.5">Track History</div>
        <div className="flex gap-1 mb-2">
          {[1, 6, 12, 24, 48].map(h => (
            <button key={h}
              onClick={() => setTrackHours(h)}
              className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
                trackHours === h ? 'bg-polar-accent text-white' : 'bg-polar-border text-slate-400 hover:text-white'
              }`}>
              {h}h
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-500">
          {trackCoords.length > 0
            ? `${trackCoords.length} position points`
            : 'No track history available'}
        </div>
      </div>

      {/* Nearby hazards */}
      {hazards && (
        <div className="space-y-2">
          <div className="text-xs text-slate-500">Nearby Hazards (200 km)</div>
          {nearestIceberg ? (
            <div className="card bg-polar-bg text-xs">
              <div className="flex items-center gap-1.5 text-orange-400 mb-1">
                <AlertTriangle className="w-3 h-3" />
                <span className="font-semibold">Nearest Iceberg</span>
              </div>
              <div className="text-white">{nearestIceberg.iceberg_name}</div>
              <div className="text-slate-500">
                {nearestIceberg.distance_km?.toFixed(0)} km away · {nearestIceberg.bearing_deg?.toFixed(0)}°
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-600">No icebergs within 200 km</div>
          )}
          {localIce && (
            <div className="card bg-polar-bg text-xs">
              <div className="text-slate-500 mb-0.5">Local Sea Ice</div>
              <div className="text-white">
                {(localIce.concentration * 100).toFixed(0)}% —{' '}
                {localIce.category.replace('_', ' ')}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function VesselsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null)
  const { setActiveVessel, setActiveVesselMmsi, activeVesselMmsi,
          updateAllVessels, setAllVessels } = useVesselStore()
  const qc = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)

  const { data: searchData, isLoading } = useQuery({
    queryKey: ['vessels-search', searchQuery],
    queryFn: () => searchVessels(searchQuery, 100),
    staleTime: 15_000,
    refetchInterval: 15_000,
  })

  const { data: activeData } = useQuery({
    queryKey: ['active-vessel'],
    queryFn: fetchActiveVessel,
    staleTime: 5_000,
    refetchInterval: 10_000,
  })

  const selectMut = useMutation({
    mutationFn: (mmsi: string) => selectVessel(mmsi),
    onSuccess: (data, mmsi) => {
      setActiveVesselMmsi(mmsi)
      if (data.vessel) setActiveVessel(data.vessel)
      qc.invalidateQueries({ queryKey: ['active-vessel'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  // Sync vessels list to Zustand store
  useEffect(() => {
    const vessels = searchData?.vessels || []
    if (vessels.length > 0) setAllVessels(vessels)
  }, [searchData])

  // WebSocket for live position updates
  useEffect(() => {
    const ws = createVesselsWebSocket((msg) => {
      if (msg.event === 'VESSEL_POSITION_UPDATED' && msg.vessel) {
        updateAllVessels(msg.vessel)
      }
      if (msg.event === 'VESSEL_REGISTRY_SNAPSHOT' && msg.vessels) {
        setAllVessels(msg.vessels)
      }
      if (msg.event === 'ACTIVE_VESSEL_CHANGED' && msg.mmsi) {
        setActiveVesselMmsi(msg.mmsi)
        if (msg.vessel) setActiveVessel(msg.vessel)
      }
    })
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const vessels: VesselSummary[] = searchData?.vessels || []
  const freshness: FreshnessInfo | null = searchData?.freshness || null
  const displayMmsi = selectedMmsi || activeVesselMmsi
  const selectedVessel = vessels.find(v => v.mmsi === displayMmsi) ||
                         activeData?.vessel || null

  const isAisConfigured = searchData?.status !== 'NOT_CONFIGURED'

  const handleSelect = async (mmsi: string) => {
    setSelectedMmsi(mmsi)
    setActiveVesselMmsi(mmsi)
    const v = vessels.find(v => v.mmsi === mmsi)
    if (v) setActiveVessel(v)
    selectMut.mutate(mmsi)
  }

  // Build vessel track for map
  const { data: trackData } = useQuery({
    queryKey: ['vessel-track-map', displayMmsi],
    queryFn: () => fetchVesselTrack(displayMmsi!, 6),
    enabled: !!displayMmsi,
    staleTime: 30_000,
  })

  const vesselForMap = selectedVessel && selectedVessel.latitude != null ? {
    mmsi: selectedVessel.mmsi,
    imo: selectedVessel.imo || '',
    vessel_name: selectedVessel.name,
    latitude: selectedVessel.latitude!,
    longitude: selectedVessel.longitude!,
    speed_knots: selectedVessel.speed,
    course_deg: selectedVessel.course,
    heading_deg: selectedVessel.heading,
    navigation_status: selectedVessel.navigation_status,
    timestamp: selectedVessel.timestamp,
    age_seconds: selectedVessel.age_seconds,
    source: selectedVessel.source,
    is_real: selectedVessel.is_real,
    data_mode: selectedVessel.data_mode,
    status_label: selectedVessel.status_label,
  } : null

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Ship}
        title="Vessel Tracking"
        subtitle="Live AIS vessel search, selection, and navigation intelligence"
        showDemoBanner={false}
      />

      {!isAisConfigured && (
        <div className="p-4 bg-amber-950/40 border border-amber-800/30 rounded-xl text-sm text-amber-400">
          <div className="font-semibold mb-1">AIS Not Configured</div>
          <p className="text-amber-600">
            Set <code className="text-amber-400">AIS_PROVIDER</code> and{' '}
            <code className="text-amber-400">AIS_API_KEY</code> in .env to enable vessel tracking.
            <br />
            Free options: <a href="https://aisstream.io" target="_blank" rel="noopener noreferrer"
              className="text-polar-accent hover:underline">AISStream.io</a> ·{' '}
            <a href="https://www.barentswatch.no/bwapi/" target="_blank" rel="noopener noreferrer"
              className="text-polar-accent hover:underline">BarentsWatch</a>
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        {/* Left: search + vessel list */}
        <div className="xl:col-span-1 space-y-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search MMSI, name, IMO..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="input-field pl-9"
            />
          </div>

          {/* Stats */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">
              {vessels.length} vessel{vessels.length !== 1 ? 's' : ''} in Antarctic region
            </span>
            <FreshnessTag freshness={freshness} compact />
          </div>

          {/* List */}
          {isLoading ? (
            <LoadingSpinner message="Loading vessels..." />
          ) : vessels.length === 0 ? (
            <div className="card text-center py-6 text-slate-500 text-sm">
              {isAisConfigured
                ? 'No vessels in Antarctic region yet. AIS stream connecting...'
                : 'Configure AIS to see vessels.'}
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
              {vessels.map(v => (
                <VesselCard
                  key={v.mmsi}
                  vessel={v}
                  isActive={v.mmsi === displayMmsi}
                  onSelect={() => handleSelect(v.mmsi)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Center: map */}
        <div className="xl:col-span-2">
          <div className="card p-0 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-polar-border">
              <div className="text-sm font-medium text-white flex items-center gap-2">
                <Navigation className="w-4 h-4 text-polar-accent" />
                {selectedVessel?.name || 'Antarctic Vessel Chart'}
              </div>
              {selectedVessel && (
                <span className={`text-xs font-bold ${selectedVessel.is_real ? 'text-emerald-400' : 'text-amber-400'}`}>
                  ● {selectedVessel.status_label}
                </span>
              )}
            </div>
            <AntarcticMap
              vessel={vesselForMap}
              vesselTrack={trackData?.track || []}
              icebergs={[]}
              layers={{
                seaIce: false, icebergs: false, trajectories: false,
                routes: false, vessel: true, vesselTrack: true,
                oceanCurrents: false, weather: false,
              }}
              height="520px"
              followVessel={!!displayMmsi}
            />
          </div>
        </div>

        {/* Right: vessel detail */}
        <div className="xl:col-span-1">
          {selectedVessel ? (
            <div className="card">
              <VesselDetailPanel vessel={selectedVessel} freshness={freshness} />
              <div className="mt-4 space-y-2">
                <button
                  onClick={() => handleSelect(selectedVessel.mmsi)}
                  disabled={selectMut.isPending}
                  className="btn-primary w-full flex items-center justify-center gap-2"
                >
                  <Activity className="w-4 h-4" />
                  {activeVesselMmsi === selectedVessel.mmsi
                    ? '✓ Active Vessel'
                    : 'Set as Active Vessel'}
                </button>
                <p className="text-xs text-slate-600 text-center">
                  Setting active vessel updates Dashboard, Routes, Analytics, and Polar Navigator.
                </p>
              </div>
            </div>
          ) : (
            <div className="card text-center py-8 text-slate-500 text-sm">
              <Ship className="w-8 h-8 mx-auto mb-3 text-slate-700" />
              Select a vessel from the list to see details and set it as the active vessel.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
