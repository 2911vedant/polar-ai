import axios from 'axios'

const BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error('API Error:', err.response?.data || err.message)
    return Promise.reject(err)
  }
)

// ── Live Data Engine ───────────────────────────────────────────────────────────
export const fetchLiveStatus     = () => api.get('/api/live/status').then(r => r.data)
export const fetchLiveLastUpdate = () => api.get('/api/live/last-update').then(r => r.data)
export const fetchLiveChanges    = () => api.get('/api/live/changes').then(r => r.data)
export const fetchLiveHistory    = (limit = 24) => api.get(`/api/live/history?limit=${limit}`).then(r => r.data)
export const triggerLiveUpdate   = () => api.post('/api/live/trigger').then(r => r.data)

// ── Health / System ────────────────────────────────────────────────────────────
export const fetchHealth       = () => api.get('/api/health').then(r => r.data)
export const fetchSystemStatus = () => api.get('/api/system/status').then(r => r.data)
export const fetchDashboard    = () => api.get('/api/dashboard').then(r => r.data)

// ── Vessels (multi-vessel) ─────────────────────────────────────────────────────
export const searchVessels       = (q = '', limit = 50) =>
  api.get(`/api/vessels?q=${encodeURIComponent(q)}&limit=${limit}`).then(r => r.data)
export const fetchActiveVessel   = () => api.get('/api/vessels/active').then(r => r.data)
export const selectVessel        = (mmsi: string) => api.post(`/api/vessels/${mmsi}/select`).then(r => r.data)
export const fetchVesselDetail   = (mmsi: string) => api.get(`/api/vessels/${mmsi}`).then(r => r.data)
export const fetchVesselPosition = (mmsi?: string) =>
  mmsi ? api.get(`/api/vessels/${mmsi}/position`).then(r => r.data)
       : api.get('/api/vessels/position').then(r => r.data)
export const fetchVesselTrack    = (hoursOrMmsi: number | string = 6, hours = 6) =>
  typeof hoursOrMmsi === 'string'
    ? api.get(`/api/vessels/${hoursOrMmsi}/track?hours=${hours}`).then(r => r.data)
    : api.get(`/api/vessels/track?hours=${hoursOrMmsi}`).then(r => r.data)
export const fetchVesselRisk     = (mmsi: string) => api.get(`/api/vessels/${mmsi}/risk`).then(r => r.data)
export const fetchVesselHazards  = (mmsi: string, radiusKm = 200) =>
  api.get(`/api/vessels/${mmsi}/nearby-hazards?radius_km=${radiusKm}`).then(r => r.data)
export const calcVesselRoute     = (mmsi: string, destLat: number, destLon: number,
                                    destName = 'Destination', routeType = 'balanced') =>
  api.post(`/api/vessels/${mmsi}/route?destination_lat=${destLat}&destination_lon=${destLon}&destination_name=${encodeURIComponent(destName)}&route_type=${routeType}`).then(r => r.data)

// ── Sea Ice ────────────────────────────────────────────────────────────────────
export const fetchSeaIceCurrent  = (resolution = 'low') => api.get(`/api/sea-ice/current?resolution=${resolution}`).then(r => r.data)
export const fetchSeaIceHistory  = (days = 90)          => api.get(`/api/sea-ice/history?days=${days}`).then(r => r.data)
export const fetchSeaIceForecast = (horizonHours = 72)  => api.get(`/api/sea-ice/forecast?horizon_hours=${horizonHours}`).then(r => r.data)

// ── Icebergs ───────────────────────────────────────────────────────────────────
export const fetchIcebergs           = () => api.get('/api/icebergs').then(r => r.data)
export const fetchIcebergDetail      = (name: string) => api.get(`/api/icebergs/${name}`).then(r => r.data)
export const fetchIcebergTrajectory  = (name: string, h = 72) => api.get(`/api/icebergs/${name}/trajectory?horizon_hours=${h}`).then(r => r.data)

// ── Satellite ──────────────────────────────────────────────────────────────────
export const fetchSatelliteLatest   = () => api.get('/api/satellite/latest').then(r => r.data)
export const fetchSatelliteProducts = () => api.get('/api/satellite/products').then(r => r.data)
export const refreshSatellite       = () => api.post('/api/satellite/refresh').then(r => r.data)

// ── Weather ────────────────────────────────────────────────────────────────────
export const fetchWeatherCurrent  = () => api.get('/api/weather/current').then(r => r.data)
export const fetchWeatherForecast = (h = 72) => api.get(`/api/weather/forecast?horizon_hours=${h}`).then(r => r.data)

// ── Ocean ──────────────────────────────────────────────────────────────────────
export const fetchOceanCurrent = () => api.get('/api/ocean/current').then(r => r.data)

// ── Risk / Routes ──────────────────────────────────────────────────────────────
export const calculateRisk  = (lat: number, lon: number, radius = 50) =>
  api.post('/api/risk/calculate', { latitude: lat, longitude: lon, radius_km: radius }).then(r => r.data)
export const generateRoutes = (params: Record<string, any>) =>
  api.post('/api/routes/generate', params).then(r => r.data)
export const compareRoutes  = (params: Record<string, any>) =>
  api.post('/api/routes/compare', params).then(r => r.data)

// ── Alerts ─────────────────────────────────────────────────────────────────────
export const fetchAlerts      = (limit = 20) => api.get(`/api/alerts?limit=${limit}`).then(r => r.data)
export const acknowledgeAlert = (id: string) => api.post(`/api/alerts/${id}/acknowledge`).then(r => r.data)

// ── Analytics / Data Sources ───────────────────────────────────────────────────
export const fetchAnalytics   = (days = 30) => api.get(`/api/analytics?days=${days}`).then(r => r.data)
export const fetchDataSources = ()          => api.get('/api/data-sources').then(r => r.data)

// ── Agent ──────────────────────────────────────────────────────────────────────
export const queryAgent = (query: string, context: Record<string, any> = {}) =>
  api.post('/api/agent/query', { query, context }).then(r => r.data)

// ── Simulation ─────────────────────────────────────────────────────────────────
export const fetchSimulationState = () => api.get('/api/simulation/state').then(r => r.data)
export const startSimulation      = () => api.post('/api/simulation/start').then(r => r.data)
export const pauseSimulation      = () => api.post('/api/simulation/pause').then(r => r.data)
export const resetSimulation      = () => api.post('/api/simulation/reset').then(r => r.data)
export const stepSimulation       = () => api.post('/api/simulation/step').then(r => r.data)

// ── WebSocket helpers ──────────────────────────────────────────────────────────
export const WS_BASE = BASE_URL.replace(/^http/, 'ws')

/** /ws/live — hourly update events, satellite, sea-ice, etc. */
export function createLiveWebSocket(onMessage: (data: any) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/live`)
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = () => {}
  return ws
}

/** /ws/vessels — all vessel position updates */
export function createVesselsWebSocket(onMessage: (data: any) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/vessels`)
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = () => {}
  return ws
}

/** /ws/vessel/:mmsi — single vessel */
export function createVesselWebSocket(onMessage: (data: any) => void, mmsi?: string) {
  const path = mmsi ? `/ws/vessel/${mmsi}` : `/api/ws/vessel`
  const ws = new WebSocket(`${WS_BASE}${path}`)
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = () => {}
  return ws
}

/** /api/alerts/stream — SSE alerts */
export function createAlertsEventSource(onAlert: (data: any) => void) {
  const es = new EventSource(`${BASE_URL}/api/alerts/stream`)
  es.addEventListener('alert', (e) => { try { onAlert(JSON.parse((e as any).data)) } catch {} })
  return es
}
