/**
 * GlobalActiveVesselBar
 * Shows at the top of every page. Displays the selected vessel with live data.
 * Clicking opens vessel selector.
 */
import { useState, useEffect, useRef } from 'react'
import { Ship, ChevronDown, Search, X, Activity } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { searchVessels } from '../services/api'
import { useVesselStore, useActiveVessel, useActiveVesselMmsi } from '../store/vesselStore'
import type { VesselSummary } from '../store/vesselStore'
import { api } from '../services/api'

export default function ActiveVesselBar() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const activeVessel = useActiveVessel()
  const activeVesselMmsi = useActiveVesselMmsi()
  const { setActiveVessel, setActiveVesselMmsi } = useVesselStore()
  const dropRef = useRef<HTMLDivElement>(null)

  const { data: searchData } = useQuery({
    queryKey: ['vessels-search-bar', q],
    queryFn: () => searchVessels(q, 20),
    enabled: open,
    staleTime: 10_000,
  })

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = async (vessel: VesselSummary) => {
    setActiveVessel(vessel)
    setActiveVesselMmsi(vessel.mmsi)
    // Tell backend
    try { await api.post(`/api/vessels/${vessel.mmsi}/select`) } catch {}
    setOpen(false)
    setQ('')
  }

  const vessels: VesselSummary[] = searchData?.vessels || []
  const ageS = activeVessel?.age_seconds || 0
  const ageStr = ageS < 60 ? `${Math.round(ageS)}s` : ageS < 3600 ? `${Math.round(ageS/60)}m` : `${Math.round(ageS/3600)}h`

  return (
    <div className="relative" ref={dropRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all text-sm ${
          activeVessel?.is_real
            ? 'border-emerald-700/50 bg-emerald-950/30 hover:bg-emerald-950/50'
            : activeVessel
              ? 'border-amber-700/50 bg-amber-950/30 hover:bg-amber-950/50'
              : 'border-polar-border bg-polar-card hover:border-slate-500'
        }`}
      >
        <Ship className={`w-3.5 h-3.5 flex-shrink-0 ${activeVessel?.is_real ? 'text-emerald-400' : activeVessel ? 'text-amber-400' : 'text-slate-500'}`} />
        <span className="text-white text-xs font-medium max-w-[140px] truncate">
          {activeVessel?.name || 'Select Vessel'}
        </span>
        {activeVessel && (
          <>
            <span className={`text-xs font-mono ${activeVessel.is_real ? 'text-emerald-400' : 'text-amber-400'}`}>
              {activeVessel.is_real ? '● LIVE' : '● DEMO'}
            </span>
            {activeVessel.is_real && (
              <span className="text-xs text-slate-500">{ageStr}</span>
            )}
          </>
        )}
        <ChevronDown className="w-3 h-3 text-slate-500 flex-shrink-0" />
      </button>

      {open && (
        <div className="absolute right-0 top-9 w-80 bg-polar-card border border-polar-border rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="p-3 border-b border-polar-border">
            <div className="text-xs text-slate-500 mb-2 font-semibold uppercase tracking-wider">
              Select Active Vessel
            </div>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
              <input
                autoFocus
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search MMSI, name..."
                className="input-field pl-8 py-1.5 text-xs"
              />
            </div>
          </div>

          <div className="max-h-64 overflow-y-auto">
            {vessels.length === 0 ? (
              <div className="px-4 py-4 text-xs text-slate-500 text-center">
                {searchData?.status === 'NOT_CONFIGURED'
                  ? 'AIS not configured'
                  : 'No vessels — AIS connecting...'}
              </div>
            ) : (
              vessels.map(v => (
                <button
                  key={v.mmsi}
                  onClick={() => handleSelect(v)}
                  className={`w-full text-left px-3 py-2.5 hover:bg-polar-border/50 transition-colors border-b border-polar-border/30 ${
                    v.mmsi === activeVesselMmsi ? 'bg-polar-accent/10' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-white text-xs font-medium">{v.name || v.mmsi}</div>
                      <div className="text-slate-500 text-xs font-mono">{v.mmsi}</div>
                    </div>
                    <span className={`text-xs ${v.is_real ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {v.status_label}
                    </span>
                  </div>
                  {v.latitude != null && (
                    <div className="text-xs text-slate-600 mt-0.5 font-mono">
                      {v.latitude.toFixed(3)}° {v.longitude?.toFixed(3)}°
                      {' · '}{v.speed?.toFixed(1)} kts
                    </div>
                  )}
                </button>
              ))
            )}
          </div>

          {activeVessel && (
            <div className="p-2 border-t border-polar-border">
              <button
                onClick={() => { useVesselStore.getState().clearActiveVessel(); setOpen(false) }}
                className="w-full text-xs text-slate-500 hover:text-red-400 transition-colors flex items-center justify-center gap-1 py-1"
              >
                <X className="w-3 h-3" /> Clear Selection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
