/**
 * POLAR-AI Active Vessel Global Store (Zustand)
 *
 * Manages:
 *  - activeVessel: the globally selected vessel
 *  - allVessels: all vessels currently in AIS registry
 *  - setActiveVessel: select a vessel (broadcasts to all pages)
 *  - updatePosition: update vessel position from WebSocket
 *
 * Persisted to localStorage so the selection survives page reloads.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { VesselPosition } from '../types'

export interface VesselSummary {
  mmsi: string
  name: string
  imo?: string
  call_sign?: string
  ship_type_name?: string
  flag?: string
  latitude: number | null
  longitude: number | null
  speed: number
  course: number
  heading: number
  navigation_status: string
  destination?: string
  eta?: string
  timestamp: string
  age_seconds: number
  source: string
  is_real: boolean
  data_mode: string
  status_label: string
}

interface VesselStore {
  // Active vessel (globally selected)
  activeVessel: VesselSummary | null
  activeVesselMmsi: string | null

  // All vessels from AIS stream
  allVessels: VesselSummary[]

  // Application mode
  dataMode: 'live' | 'demo'

  // Actions
  setActiveVessel: (vessel: VesselSummary | null) => void
  setActiveVesselMmsi: (mmsi: string | null) => void
  updateVesselPosition: (vessel: VesselSummary) => void
  setAllVessels: (vessels: VesselSummary[]) => void
  updateAllVessels: (vessel: VesselSummary) => void
  setDataMode: (mode: 'live' | 'demo') => void
  clearActiveVessel: () => void
}

export const useVesselStore = create<VesselStore>()(
  persist(
    (set, get) => ({
      activeVessel: null,
      activeVesselMmsi: null,
      allVessels: [],
      dataMode: 'live',

      setActiveVessel: (vessel) => {
        set({
          activeVessel: vessel,
          activeVesselMmsi: vessel?.mmsi ?? null,
        })
      },

      setActiveVesselMmsi: (mmsi) => {
        set({ activeVesselMmsi: mmsi })
        // Try to find vessel in allVessels
        const found = get().allVessels.find(v => v.mmsi === mmsi)
        if (found) set({ activeVessel: found })
      },

      updateVesselPosition: (vessel) => {
        set(state => {
          const isActive = state.activeVesselMmsi === vessel.mmsi
          return {
            activeVessel: isActive ? vessel : state.activeVessel,
            allVessels: state.allVessels.map(v =>
              v.mmsi === vessel.mmsi ? vessel : v
            ),
          }
        })
      },

      setAllVessels: (vessels) => {
        set(state => {
          // Update active vessel if present in the new list
          const active = vessels.find(v => v.mmsi === state.activeVesselMmsi)
          return {
            allVessels: vessels,
            activeVessel: active ?? state.activeVessel,
          }
        })
      },

      updateAllVessels: (vessel) => {
        set(state => {
          const exists = state.allVessels.some(v => v.mmsi === vessel.mmsi)
          const newAll = exists
            ? state.allVessels.map(v => v.mmsi === vessel.mmsi ? vessel : v)
            : [...state.allVessels, vessel]
          const isActive = state.activeVesselMmsi === vessel.mmsi
          return {
            allVessels: newAll,
            activeVessel: isActive ? vessel : state.activeVessel,
          }
        })
      },

      setDataMode: (mode) => set({ dataMode: mode }),

      clearActiveVessel: () => set({
        activeVessel: null,
        activeVesselMmsi: null,
      }),
    }),
    {
      name: 'polar-ai-vessel-store',
      // Only persist the selection (MMSI) — not the full vessel data (stale after restart)
      partialize: (state) => ({
        activeVesselMmsi: state.activeVesselMmsi,
        dataMode: state.dataMode,
      }),
    }
  )
)

// ── Selector hooks ─────────────────────────────────────────────────────────────

export const useActiveVessel      = () => useVesselStore(s => s.activeVessel)
export const useActiveVesselMmsi  = () => useVesselStore(s => s.activeVesselMmsi)
export const useAllVessels        = () => useVesselStore(s => s.allVessels)
export const useDataMode          = () => useVesselStore(s => s.dataMode)

/** Returns true if there is a real (not demo) active vessel with a known position */
export const useHasLiveVessel = () => useVesselStore(s =>
  !!(s.activeVessel?.is_real && s.activeVessel?.latitude != null)
)
