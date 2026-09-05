import { useQuery } from '@tanstack/react-query'
import { BarChart3, TrendingUp, TrendingDown } from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, PieChart, Pie, Cell, Area, AreaChart
} from 'recharts'
import { fetchAnalytics } from '../services/api'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'

const PIE_COLORS = ['#0ea5e9', '#22c55e', '#f59e0b', '#a855f7', '#ef4444', '#67e8f9']

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics-30'],
    queryFn: () => fetchAnalytics(30),
    staleTime: 300_000,
  })

  if (isLoading) return <LoadingSpinner message="Loading analytics..." size="lg" />

  const iceTrend = data?.sea_ice_trend || []
  const icebergTrend = data?.iceberg_count_trend || []
  const riskTrend = data?.route_risk_trend || []
  const accuracy = data?.forecast_accuracy || []
  const weatherDist = data?.weather_distribution || []
  const fuelEff = data?.fuel_efficiency_by_route || []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={BarChart3}
        title="Analytics"
        subtitle="Historical trends, model performance, and operational metrics"
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Avg Ice Coverage', value: `${data?.summary?.avg_sea_ice_coverage?.toFixed(1)}%`, icon: TrendingUp, color: '#67e8f9' },
          { label: 'Avg Iceberg Count', value: data?.summary?.avg_iceberg_count?.toFixed(0), icon: TrendingUp, color: '#f97316' },
          { label: 'Avg Route Risk', value: `${(data?.summary?.avg_route_risk * 100)?.toFixed(0)}/100`, icon: TrendingDown, color: '#f59e0b' },
          { label: 'Best Skill Score', value: `${(data?.summary?.best_skill_score * 100)?.toFixed(0)}%`, icon: TrendingUp, color: '#22c55e' },
        ].map(s => (
          <div key={s.label} className="card flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: s.color + '20' }}>
              <s.icon className="w-4 h-4" style={{ color: s.color }} />
            </div>
            <div>
              <div className="text-xs text-slate-500">{s.label}</div>
              <div className="text-xl font-bold text-white">{s.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Sea ice trend */}
        <div className="card">
          <div className="text-sm font-semibold text-white mb-4">Sea Ice Coverage Trend (30 days)</div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={iceTrend}>
              <defs>
                <linearGradient id="iceTrendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#67e8f9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#67e8f9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval={4} />
              <YAxis domain={[30, 70]} tick={{ fill: '#64748b', fontSize: 10 }} unit="%" />
              <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }} itemStyle={{ color: '#67e8f9' }} />
              <Area type="monotone" dataKey="coverage_pct" stroke="#67e8f9" fill="url(#iceTrendGrad)" strokeWidth={2} name="Coverage %" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Iceberg count trend */}
        <div className="card">
          <div className="text-sm font-semibold text-white mb-4">Active Iceberg Count (30 days)</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={icebergTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval={4} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }} itemStyle={{ color: '#f97316' }} />
              <Bar dataKey="count" fill="#f97316" opacity={0.8} radius={[2, 2, 0, 0]} name="Icebergs" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Forecast accuracy */}
        <div className="card">
          <div className="text-sm font-semibold text-white mb-4">Forecast Accuracy by Horizon</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={accuracy} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" horizontal={false} />
              <XAxis type="number" domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} />
              <YAxis type="category" dataKey="horizon" tick={{ fill: '#94a3b8', fontSize: 11 }} width={30} />
              <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }} formatter={(v: any) => [`${(v*100).toFixed(1)}%`]} />
              <Bar dataKey="skill_score" fill="#0ea5e9" radius={[0, 3, 3, 0]} name="Skill Score" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Weather distribution */}
        <div className="card">
          <div className="text-sm font-semibold text-white mb-4">Weather Conditions Distribution</div>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={weatherDist} dataKey="frequency_pct" nameKey="condition" cx="50%" cy="50%" outerRadius={65} label={({ condition, frequency_pct }) => `${condition}: ${frequency_pct}%`} labelLine={false}>
                {weatherDist.map((_: any, i: number) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Fuel efficiency */}
        <div className="card">
          <div className="text-sm font-semibold text-white mb-4">Route Fuel Efficiency</div>
          <div className="space-y-3">
            {fuelEff.map((r: any) => (
              <div key={r.route_type}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">{r.route_type}</span>
                  <span className="text-white font-mono">{(r.avg_fuel_index * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 bg-polar-border rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(r.avg_fuel_index * 100, 100)}%`,
                      background: r.route_type === 'Fuel Efficient' ? '#22c55e' :
                                  r.route_type === 'Shortest' ? '#f59e0b' : '#0ea5e9'
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Route risk trend */}
      <div className="card">
        <div className="text-sm font-semibold text-white mb-4">Route Risk Trend (30 days)</div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={riskTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval={4} />
            <YAxis domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(v) => `${(v*100).toFixed(0)}`} />
            <Tooltip
              contentStyle={{ background: '#0d1220', border: '1px solid #1a2540', borderRadius: 8 }}
              formatter={(v: any) => [`${(v*100).toFixed(0)}/100`]}
            />
            <Line type="monotone" dataKey="risk_score" stroke="#f97316" strokeWidth={2} dot={false} name="Risk Score" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
