import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, Play, Pause, RotateCcw, ChevronRight, AlertTriangle, CheckCircle } from 'lucide-react'
import { fetchSimulationState, startSimulation, pauseSimulation, resetSimulation, stepSimulation } from '../services/api'
import PageHeader from '../components/PageHeader'
import AntarcticMap from '../components/AntarcticMap'
import RiskGauge from '../components/RiskGauge'
import type { SimulationState, SimulationEvent } from '../types'

export default function SimulationPage() {
  const [autoStep, setAutoStep] = useState(false)
  const qc = useQueryClient()

  const { data: state } = useQuery<SimulationState>({
    queryKey: ['simulation'],
    queryFn: fetchSimulationState,
    refetchInterval: autoStep ? 1000 : false,
  })

  const startMut = useMutation({ mutationFn: startSimulation, onSuccess: d => { qc.setQueryData(['simulation'], d); setAutoStep(true) } })
  const pauseMut = useMutation({ mutationFn: pauseSimulation, onSuccess: d => { qc.setQueryData(['simulation'], d); setAutoStep(false) } })
  const resetMut = useMutation({ mutationFn: resetSimulation, onSuccess: d => { qc.setQueryData(['simulation'], d); setAutoStep(false) } })
  const stepMut  = useMutation({ mutationFn: stepSimulation, onSuccess: d => { qc.setQueryData(['simulation'], d) } })

  // Auto-step
  useEffect(() => {
    if (!autoStep || state?.scenario_complete) {
      setAutoStep(false)
      return
    }
    const timer = setInterval(() => stepMut.mutate(), 800)
    return () => clearInterval(timer)
  }, [autoStep, state?.scenario_complete])

  const riskScore = state ? state.risk_score * 100 : 0
  const routeStatus = state?.route_status || 'original'

  const routeStatusColor = routeStatus === 'replanned' ? '#22c55e' :
                           routeStatus === 'recalculating' ? '#f59e0b' : '#0ea5e9'

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        icon={Cpu}
        title="Simulation Mode"
        subtitle="Dynamic iceberg-vessel scenario — watch POLAR-AI auto-replan routes"
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Controls + events */}
        <div className="space-y-4">
          {/* Playback controls */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3">Playback Controls</div>
            <div className="flex gap-2 mb-4">
              {!state?.running || !autoStep ? (
                <button
                  onClick={() => startMut.mutate()}
                  disabled={state?.scenario_complete}
                  className="btn-primary flex items-center gap-1.5"
                >
                  <Play className="w-4 h-4" /> Start
                </button>
              ) : (
                <button onClick={() => pauseMut.mutate()} className="btn-secondary flex items-center gap-1.5">
                  <Pause className="w-4 h-4" /> Pause
                </button>
              )}
              <button onClick={() => stepMut.mutate()} disabled={state?.scenario_complete} className="btn-secondary">
                <ChevronRight className="w-4 h-4" />
              </button>
              <button onClick={() => resetMut.mutate()} className="btn-secondary flex items-center gap-1.5">
                <RotateCcw className="w-4 h-4" /> Reset
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <div className="text-slate-500">Step</div>
                <div className="text-white font-mono">{state?.step || 0}/60</div>
              </div>
              <div>
                <div className="text-slate-500">Sim Time</div>
                <div className="text-white font-mono">T+{state?.time_offset_hours?.toFixed(1) || 0}h</div>
              </div>
              <div>
                <div className="text-slate-500">Route</div>
                <div className="font-mono capitalize" style={{ color: routeStatusColor }}>
                  {routeStatus}
                </div>
              </div>
              <div>
                <div className="text-slate-500">Status</div>
                <div className={`font-mono ${state?.scenario_complete ? 'text-emerald-400' : autoStep ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {state?.scenario_complete ? 'Complete' : autoStep ? 'Running' : 'Paused'}
                </div>
              </div>
            </div>
          </div>

          {/* Risk */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3">Live Risk Score</div>
            <RiskGauge score={riskScore} label="Navigation Risk" size="lg" />
            {routeStatus === 'replanned' && (
              <div className="mt-3 flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle className="w-3 h-3" />
                Route recalculated — risk reduced
              </div>
            )}
            {routeStatus === 'recalculating' && (
              <div className="mt-3 flex items-center gap-2 text-xs text-amber-400 animate-pulse">
                <AlertTriangle className="w-3 h-3" />
                POLAR-AI recalculating route...
              </div>
            )}
          </div>

          {/* Event log */}
          <div className="card">
            <div className="text-sm font-semibold text-white mb-3">Scenario Events</div>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {(state?.events || []).map((ev: SimulationEvent, i: number) => (
                <div
                  key={i}
                  className={`flex gap-2 text-xs ${
                    ev.is_alert ? 'text-amber-400' : 'text-slate-400'
                  }`}
                >
                  <span className="font-mono text-slate-600 w-8 flex-shrink-0">T+{ev.step}</span>
                  <span className="leading-relaxed">{ev.message}</span>
                </div>
              ))}
              {(!state?.events || state.events.length === 0) && (
                <div className="text-xs text-slate-600">Press Start to begin scenario</div>
              )}
            </div>
          </div>
        </div>

        {/* Map + vessel/iceberg info */}
        <div className="xl:col-span-2 space-y-4">
          <AntarcticMap
            icebergs={state?.icebergs || []}
            //
            //
            //
            //
            //
            //
            height="420px"
          />

          {/* Vessel + scenario info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <div className="text-sm font-semibold text-white mb-3">Vessel Position</div>
              <div className="space-y-2 text-xs">
                {[
                  ['Latitude', `${state?.vessel?.latitude?.toFixed(4) || '--'}°S`],
                  ['Longitude', `${state?.vessel?.longitude?.toFixed(4) || '--'}°`],
                  ['Speed', `${state?.vessel?.speed_knots?.toFixed(1) || '--'} kts`],
                  ['Heading', `${state?.vessel?.heading_deg?.toFixed(0) || '--'}°`],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between">
                    <span className="text-slate-500">{label}</span>
                    <span className="text-white font-mono">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="text-sm font-semibold text-white mb-3">Scenario Progress</div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Progress</span>
                  <span className="text-polar-accent">{state?.step || 0}/60 steps</span>
                </div>
                <div className="h-2 bg-polar-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-polar-accent rounded-full transition-all"
                    style={{ width: `${((state?.step || 0) / 60) * 100}%` }}
                  />
                </div>
                <div className="text-xs space-y-1 mt-3">
                  {[
                    { step: 10, label: 'Iceberg detected' },
                    { step: 22, label: 'Route becomes unsafe' },
                    { step: 25, label: 'Route recalculated' },
                    { step: 50, label: 'Scenario complete' },
                  ].map(milestone => (
                    <div key={milestone.step} className={`flex items-center gap-2 ${(state?.step || 0) >= milestone.step ? 'text-emerald-400' : 'text-slate-600'}`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${(state?.step || 0) >= milestone.step ? 'bg-emerald-400' : 'bg-slate-700'}`} />
                      Step {milestone.step}: {milestone.label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {state?.scenario_complete && (
            <div className="p-4 bg-emerald-950/40 border border-emerald-700/40 rounded-xl text-sm text-emerald-400 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <div>
                <div className="font-semibold">Scenario Complete</div>
                <div className="text-xs text-emerald-600 mt-0.5">
                  POLAR-AI successfully detected the iceberg threat, recalculated the route, and guided the vessel safely.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
