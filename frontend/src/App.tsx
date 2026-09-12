import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Snowflake, Mountain, Navigation,
  BarChart3, Database, Bot, Cpu, Ship,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchSystemStatus } from './services/api'
import DashboardPage    from './pages/DashboardPage'
import SeaIcePage       from './pages/SeaIcePage'
import IcebergPage      from './pages/IcebergPage'
import RoutePlannerPage from './pages/RoutePlannerPage'
import AnalyticsPage    from './pages/AnalyticsPage'
import DataSourcesPage  from './pages/DataSourcesPage'
import NavigatorPage    from './pages/NavigatorPage'
import SimulationPage   from './pages/SimulationPage'
import VesselsPage      from './pages/VesselsPage'
import SystemStatusBar  from './components/SystemStatusBar'
import AlertBell        from './components/AlertBell'
import LiveDataEngine   from './components/LiveDataEngine'
import ActiveVesselBar  from './components/ActiveVesselBar'

const NAV = [
  { path: '/',             icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/vessels',      icon: Ship,            label: 'Vessels' },
  { path: '/sea-ice',      icon: Snowflake,       label: 'Sea Ice' },
  { path: '/icebergs',     icon: Mountain,        label: 'Icebergs' },
  { path: '/routes',       icon: Navigation,      label: 'Route Planner' },
  { path: '/analytics',    icon: BarChart3,       label: 'Analytics' },
  { path: '/simulation',   icon: Cpu,             label: 'Simulation' },
  { path: '/navigator',    icon: Bot,             label: 'Polar Navigator' },
  { path: '/data-sources', icon: Database,        label: 'Data Sources' },
]

function Sidebar() {
  const { data: status } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    refetchInterval: 30_000,
  })
  const mode     = status?.effective_data_mode || 'live'
  const isDemo   = mode === 'demo'
  const liveCount = (status?.live || 0) + (status?.near_real_time || 0)

  return (
    <aside className="w-60 flex-shrink-0 flex flex-col bg-polar-card border-r border-polar-border h-screen overflow-hidden">
      {/* Logo */}
      <div className="p-4 border-b border-polar-border flex-shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 rounded-lg bg-polar-accent/20 border border-polar-accent/40 flex items-center justify-center">
            <Snowflake className="w-4 h-4 text-polar-accent" />
          </div>
          <div>
            <div className="font-bold text-white text-sm tracking-wider">POLAR-AI</div>
            <div className="text-xs text-slate-500">SIH26059 · v2</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-1.5">
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDemo ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
          <span className={`text-xs font-mono font-bold ${isDemo ? 'text-amber-400' : 'text-emerald-400'}`}>
            {isDemo ? 'DEMO MODE' : `LIVE · ${liveCount} sources`}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-shrink-0 p-3 space-y-0.5">
        {NAV.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => isActive ? 'nav-link-active' : 'nav-link'}
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Live Data Engine */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="border-t border-polar-border pt-3">
          <LiveDataEngine compact={false} />
        </div>
      </div>

      <div className="px-3 pb-3 flex-shrink-0">
        <p className="text-xs text-slate-700 leading-tight border border-polar-border rounded p-2">
          {isDemo ? 'DEMO/SIMULATION DATA' : 'LIVE DATA MODE'}<br />
          Decision support only. Not a certified navigation system.
        </p>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-polar-bg pb-8">
          {/* Top bar with active vessel selector + alert bell */}
          <div className="sticky top-0 z-40 flex items-center justify-between px-6 py-2 bg-polar-bg/95 backdrop-blur border-b border-polar-border">
            <span className="text-xs text-slate-600 font-mono">
              POLAR-AI Antarctic Navigation Intelligence
            </span>
            <div className="flex items-center gap-3">
              <ActiveVesselBar />
              <AlertBell />
            </div>
          </div>

          <Routes>
            <Route path="/"             element={<DashboardPage />} />
            <Route path="/vessels"      element={<VesselsPage />} />
            <Route path="/sea-ice"      element={<SeaIcePage />} />
            <Route path="/icebergs"     element={<IcebergPage />} />
            <Route path="/routes"       element={<RoutePlannerPage />} />
            <Route path="/analytics"    element={<AnalyticsPage />} />
            <Route path="/simulation"   element={<SimulationPage />} />
            <Route path="/navigator"    element={<NavigatorPage />} />
            <Route path="/data-sources" element={<DataSourcesPage />} />
          </Routes>
        </main>
      </div>
      <SystemStatusBar />
    </BrowserRouter>
  )
}
