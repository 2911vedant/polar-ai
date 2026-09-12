import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { GridPoint, Iceberg, Route, TrajectoryPoint, OceanPoint, WeatherPoint } from '../types'
import { getSicColor } from '../utils/risk'
import type { VesselSummary } from '../store/vesselStore'

// Fix Leaflet default marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

export interface MapLayers {
  seaIce?: boolean
  icebergs?: boolean
  trajectories?: boolean
  routes?: boolean
  vessel?: boolean
  vesselTrack?: boolean
  allVessels?: boolean
  oceanCurrents?: boolean
  weather?: boolean
  riskZones?: boolean
  satellite?: boolean
}

interface AntarcticMapProps {
  seaIceGrid?: GridPoint[]
  icebergs?: Iceberg[]
  routes?: Route[]
  selectedRoute?: Route | null
  trajectories?: Map<string, TrajectoryPoint[]>
  vessel?: any | null
  allVessels?: VesselSummary[]
  vesselTrack?: Array<{ latitude: number; longitude: number }>
  oceanGrid?: OceanPoint[]
  weatherGrid?: WeatherPoint[]
  satelliteFootprint?: any
  satelliteOpacity?: number
  seaIceOpacity?: number
  layers?: MapLayers
  height?: string
  followVessel?: boolean
  onIcebergClick?: (iceberg: Iceberg) => void
  onMapClick?: (lat: number, lon: number) => void
  onVesselClick?: (vessel: VesselSummary) => void
}

const DEFAULT_LAYERS: MapLayers = {
  seaIce: true, icebergs: true, trajectories: true,
  routes: true, vessel: true, vesselTrack: false,
  oceanCurrents: false, weather: false, riskZones: false, satellite: true,
}

export default function AntarcticMap({
  seaIceGrid = [],
  icebergs = [],
  routes = [],
  selectedRoute = null,
  trajectories = new Map(),
  vessel = null,
  allVessels = [],
  vesselTrack = [],
  oceanGrid = [],
  weatherGrid = [],
  satelliteFootprint = null,
  satelliteOpacity = 0.6,
  seaIceOpacity = 0.7,
  layers = DEFAULT_LAYERS,
  height = '500px',
  followVessel = false,
  onIcebergClick,
  onMapClick,
  onVesselClick,
}: AntarcticMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<L.Map | null>(null)
  const layerGroups = useRef<Record<string, L.LayerGroup>>({})

  // ── Init map ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return

    const map = L.map(mapRef.current, {
      center: [-70, 0], zoom: 3, minZoom: 2, maxZoom: 9,
    })

    // Stadia Alidade Smooth Dark — free, no API key
    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', {
      attribution: '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> | POLAR-AI',
      maxZoom: 20,
    }).addTo(map)

    // Click handler
    if (onMapClick) {
      map.on('click', (e) => onMapClick(e.latlng.lat, e.latlng.lng))
    }

    const groups: Record<string, L.LayerGroup> = {}
    for (const key of ['seaIce','icebergs','trajectories','routes','vessel',
                        'vesselTrack','allVessels','ocean','weather','satellite']) {
      groups[key] = L.layerGroup().addTo(map)
    }

    mapInstance.current = map
    layerGroups.current = groups

    return () => { map.remove(); mapInstance.current = null }
  }, [])

  // ── Sea Ice layer ────────────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.seaIce
    if (!lg) return
    lg.clearLayers()
    if (!layers.seaIce || !seaIceGrid.length) return

    const cellSize = seaIceGrid.length > 300 ? 2.0 : 1.5
    seaIceGrid.forEach(pt => {
      if (pt.concentration < 0.10) return
      const color = getSicColor(pt.concentration)
      const opacity = Math.max(0.15, pt.concentration * seaIceOpacity)
      L.rectangle(
        [[pt.latitude - cellSize / 2, pt.longitude - cellSize / 2],
         [pt.latitude + cellSize / 2, pt.longitude + cellSize / 2]],
        { color: 'transparent', fillColor: color, fillOpacity: opacity, weight: 0 }
      )
        .bindTooltip(`SIC: ${(pt.concentration * 100).toFixed(0)}% — ${pt.ice_category.replace('_', ' ')}`, { sticky: true })
        .addTo(lg)
    })
  }, [seaIceGrid, layers.seaIce, seaIceOpacity])

  // ── Icebergs layer ───────────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.icebergs
    const tl = layerGroups.current.trajectories
    if (!lg || !tl) return
    lg.clearLayers()
    tl.clearLayers()
    if (!layers.icebergs || !icebergs.length) return

    icebergs.forEach((ib, i) => {
      const color = ib.risk_level === 'high' || ib.risk_level === 'critical' ? '#ef4444' :
                    ib.risk_level === 'medium' ? '#f97316' : '#f59e0b'
      const radius = 5 + Math.min(2.5, (ib.length_km || 20) / 80) * 4
      const isReal = (ib as any).is_real

      // Pulsing ring for high-risk
      if (ib.risk_level === 'high' || ib.risk_level === 'critical') {
        L.circle([ib.latitude, ib.longitude], {
          radius: 40000, color, fillColor: color,
          fillOpacity: 0.08, weight: 1.5, dashArray: '4 4',
        }).addTo(lg)
      }

      const marker = L.circleMarker([ib.latitude, ib.longitude], {
        radius, fillColor: color, color: '#0a0e1a', weight: 1.5, fillOpacity: 0.9,
      })
        .bindTooltip(
          `<b>${ib.iceberg_name}</b>${isReal ? ' 🟢' : ' (demo)'}<br/>` +
          `${ib.length_km?.toFixed(0) ?? '?'} × ${ib.width_km?.toFixed(0) ?? '?'} km<br/>` +
          `Speed: ${ib.drift_speed_kmh?.toFixed(2) ?? '?'} km/h<br/>` +
          `Risk: <b style="color:${color}">${ib.risk_level.toUpperCase()}</b>`,
          { sticky: false }
        )

      if (onIcebergClick) marker.on('click', () => onIcebergClick(ib))
      marker.addTo(lg)

      // Trajectory
      if (layers.trajectories) {
        const traj = trajectories.get(ib.iceberg_name)
        if (traj?.length) {
          const coords: [number, number][] = [
            [ib.latitude, ib.longitude],
            ...traj.map(tp => [tp.latitude, tp.longitude] as [number, number]),
          ]
          L.polyline(coords, { color, weight: 2, opacity: 0.65, dashArray: '5 4' }).addTo(tl)
          // Uncertainty circles at 24h and 72h
          traj.filter(tp => tp.horizon_hours === 24 || tp.horizon_hours === 72).forEach(tp => {
            if (tp.uncertainty_km) {
              L.circle([tp.latitude, tp.longitude], {
                radius: tp.uncertainty_km * 1000,
                color, fillColor: color, fillOpacity: 0.05, weight: 1,
              }).bindTooltip(`+${tp.horizon_hours}h ±${tp.uncertainty_km.toFixed(0)} km`).addTo(tl)
            }
            L.circleMarker([tp.latitude, tp.longitude], {
              radius: 4, fillColor: color, color: '#fff', weight: 1, fillOpacity: 0.9,
            }).bindTooltip(`${ib.iceberg_name} +${tp.horizon_hours}h`).addTo(tl)
          })
        }
      }
    })
  }, [icebergs, layers.icebergs, layers.trajectories, trajectories, onIcebergClick])

  // ── Routes layer ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.routes
    if (!lg) return
    lg.clearLayers()
    if (!layers.routes || !routes.length) return

    const COLORS: Record<string, string> = {
      shortest: '#f59e0b', safest: '#22c55e',
      fuel_efficient: '#0ea5e9', balanced: '#a855f7', replanned_safe: '#22c55e',
    }

    routes.forEach((route, idx) => {
      const coords: [number, number][] = route.waypoints.map(wp => [wp.latitude, wp.longitude])
      if (coords.length < 2) return
      const color = COLORS[route.route_type] || '#94a3b8'
      const isSelected = selectedRoute?.id === route.id
      L.polyline(coords, {
        color, weight: isSelected ? 4 : 2,
        opacity: isSelected ? 0.95 : 0.55,
        dashArray: isSelected ? undefined : '7 5',
      })
        .bindTooltip(
          `<b>${route.route_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</b><br/>` +
          `${route.total_distance_km.toFixed(0)} km · ${route.estimated_duration_hours.toFixed(0)}h · ` +
          `Risk ${(route.overall_risk_score * 100).toFixed(0)}/100`,
          { sticky: true }
        )
        .addTo(lg)

      // Origin / destination on first route only
      if (idx === 0 && coords.length) {
        L.circleMarker(coords[0], { radius: 9, fillColor: '#22c55e', color: '#fff', weight: 2, fillOpacity: 1 })
          .bindTooltip(route.origin_name).addTo(lg)
        L.circleMarker(coords[coords.length - 1], { radius: 9, fillColor: '#ef4444', color: '#fff', weight: 2, fillOpacity: 1 })
          .bindTooltip(route.destination_name).addTo(lg)
      }
    })
  }, [routes, selectedRoute, layers.routes])

  // ── Vessel layer ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.vessel
    const tl = layerGroups.current.vesselTrack
    if (!lg) return
    lg.clearLayers()
    if (tl) tl.clearLayers()

    if (!layers.vessel) return

    const lat = vessel?.latitude ?? -66.0
    const lon = vessel?.longitude ?? -60.0
    const heading = vessel?.heading_deg ?? 145
    const isReal = vessel?.is_real ?? false
    const statusColor = isReal ? '#22c55e' : '#f59e0b'
    const label = vessel?.status_label ?? 'DEMO'

    // Directional vessel icon (rotated triangle)
    const vesselIcon = L.divIcon({
      html: `
        <div style="position:relative;width:28px;height:28px;">
          <div style="
            width:0;height:0;
            border-left:10px solid transparent;
            border-right:10px solid transparent;
            border-bottom:22px solid ${statusColor};
            transform:rotate(${heading}deg);
            transform-origin:50% 50%;
            position:absolute;top:3px;left:4px;
            filter:drop-shadow(0 0 4px ${statusColor}88);
          "></div>
          <div style="
            position:absolute;bottom:-16px;left:50%;transform:translateX(-50%);
            background:${statusColor};color:#000;font-size:8px;font-weight:bold;
            padding:0 3px;border-radius:2px;white-space:nowrap;
          ">${label}</div>
        </div>`,
      className: '',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    })

    L.marker([lat, lon], { icon: vesselIcon })
      .bindTooltip(
        `<b>${vessel?.vessel_name ?? 'RV Polar Explorer'}</b><br/>` +
        `${isReal ? '🟢 LIVE AIS' : '🟡 DEMO'}<br/>` +
        `${lat.toFixed(4)}°S, ${lon.toFixed(4)}°<br/>` +
        `${vessel?.speed_knots?.toFixed(1) ?? '?'} kts · ${heading.toFixed(0)}°`
      )
      .addTo(lg)

    // 50 km awareness ring
    L.circle([lat, lon], {
      radius: 50000, color: statusColor, fillColor: statusColor,
      fillOpacity: 0.04, weight: 1, dashArray: '4 4',
    }).addTo(lg)

    // Follow vessel
    if (followVessel && mapInstance.current) {
      mapInstance.current.panTo([lat, lon])
    }

    // Vessel track
    if (layers.vesselTrack && tl && vesselTrack.length > 1) {
      const trackCoords: [number, number][] = vesselTrack.map(p => [p.latitude, p.longitude])
      L.polyline(trackCoords, { color: statusColor, weight: 2, opacity: 0.5, dashArray: '3 3' }).addTo(tl)
    }
  }, [vessel, vesselTrack, layers.vessel, layers.vesselTrack, followVessel])

  // ── Ocean current vectors ─────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.ocean
    if (!lg) return
    lg.clearLayers()
    if (!layers.oceanCurrents || !oceanGrid.length) return

    oceanGrid.forEach(pt => {
      const speed = pt.current_speed_ms
      const dir = pt.current_direction_deg
      if (speed < 0.05) return

      // Arrow length proportional to speed (max 1° for 0.5 m/s)
      const arrowLen = Math.min(1.5, speed * 2.5)
      const rad = (dir * Math.PI) / 180
      const endLat = pt.latitude + arrowLen * Math.cos(rad)
      const endLon = pt.longitude + arrowLen * Math.sin(rad)

      const color = speed > 0.4 ? '#ef4444' : speed > 0.25 ? '#f97316' : '#0ea5e9'

      L.polyline([[pt.latitude, pt.longitude], [endLat, endLon]], {
        color, weight: 2, opacity: 0.8,
      })
        .bindTooltip(
          `Current: ${speed.toFixed(3)} m/s · ${dir.toFixed(0)}°<br/>` +
          `${pt.sea_surface_temp_celsius != null ? `SST: ${pt.sea_surface_temp_celsius.toFixed(1)}°C` : ''}`,
          { sticky: true }
        )
        .addTo(lg)

      // Arrowhead
      L.circleMarker([endLat, endLon], {
        radius: 2.5, fillColor: color, color, weight: 1, fillOpacity: 1,
      }).addTo(lg)
    })
  }, [oceanGrid, layers.oceanCurrents])

  // ── All Vessels layer (other vessels besides active) ─────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.allVessels
    if (!lg) return
    lg.clearLayers()
    if (!layers.allVessels || !allVessels.length) return

    allVessels.forEach(v => {
      if (v.latitude == null || v.longitude == null) return
      const isActive = v.mmsi === vessel?.mmsi
      if (isActive) return // active vessel rendered by vessel layer

      const color = v.is_real ? '#22c55e' : '#f59e0b'
      const marker = L.circleMarker([v.latitude, v.longitude], {
        radius: 5, fillColor: color, color: '#0a0e1a', weight: 1.5, fillOpacity: 0.85,
      }).bindTooltip(
        `<b>${v.name || v.mmsi}</b><br/>${v.mmsi}<br/>` +
        `${v.speed?.toFixed(1)} kts · ${v.heading?.toFixed(0)}°<br/>` +
        `${v.is_real ? '🟢 LIVE' : '🟡 DEMO'}`,
        { sticky: false }
      )
      if (onVesselClick) marker.on('click', () => onVesselClick(v))
      marker.addTo(lg)
    })
  }, [allVessels, layers.allVessels, vessel?.mmsi, onVesselClick])

  // ── Satellite footprint ───────────────────────────────────────────────────────
  useEffect(() => {
    const lg = layerGroups.current.satellite
    if (!lg) return
    lg.clearLayers()
    if (!layers.satellite || !satelliteFootprint) return

    try {
      const style = {
        color: '#67e8f9', fillColor: '#67e8f9',
        fillOpacity: satelliteOpacity * 0.12, weight: 1.5, dashArray: '6 3',
      }
      if (satelliteFootprint.type === 'Polygon') {
        const coords = satelliteFootprint.coordinates[0].map((c: number[]) => [c[1], c[0]] as [number, number])
        L.polygon(coords, style)
          .bindTooltip('Sentinel-1 SAR acquisition footprint')
          .addTo(lg)
      } else if (satelliteFootprint.type === 'Feature') {
        const coords = satelliteFootprint.geometry.coordinates[0].map((c: number[]) => [c[1], c[0]] as [number, number])
        L.polygon(coords, style).addTo(lg)
      }
    } catch (e) {
      // Invalid geometry — skip silently
    }
  }, [satelliteFootprint, layers.satellite, satelliteOpacity])

  return (
    <div ref={mapRef} className="w-full rounded-xl border border-polar-border" style={{ height }} />
  )
}

// ── All-vessels layer ─────────────────────────────────────────────────────────
// This export is appended at module level — actual hook wired in via useEffect
// in the component. The allVessels useEffect is handled inline in the component.
