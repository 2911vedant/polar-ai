import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bot, Send, Snowflake, Loader2, Wrench } from 'lucide-react'
import { queryAgent } from '../services/api'
import PageHeader from '../components/PageHeader'
import { useActiveVessel } from '../store/vesselStore'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  llm_provider?: string
  timestamp: string
}

const SUGGESTIONS = [
  'Which route is safest to Rothera Station?',
  'Why is the current navigation risk high?',
  'Which icebergs are most dangerous?',
  'What is the current sea ice forecast?',
  'What are the weather conditions now?',
  'Where is the vessel and what is its status?',
  'Compare shortest vs safest route',
  'Should we proceed given current conditions?',
]

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
        isUser ? 'bg-polar-accent/20 border border-polar-accent/30' : 'bg-slate-700/50 border border-slate-600/30'
      }`}>
        {isUser ? (
          <span className="text-xs text-polar-accent">You</span>
        ) : (
          <Snowflake className="w-3.5 h-3.5 text-polar-accent" />
        )}
      </div>
      <div className={`max-w-[80%] space-y-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-3 rounded-xl text-sm leading-relaxed ${
          isUser
            ? 'bg-polar-accent/20 border border-polar-accent/20 text-white'
            : 'bg-polar-card border border-polar-border text-slate-200'
        }`}>
          {msg.content.split('\n').map((line, i) => {
            if (line.startsWith('**') && line.endsWith('**')) {
              return <p key={i} className="font-semibold text-white">{line.replace(/\*\*/g, '')}</p>
            }
            if (line.startsWith('•') || line.startsWith('→')) {
              return <p key={i} className="ml-2 text-slate-300">{line}</p>
            }
            if (line.startsWith('>')) {
              return <p key={i} className="text-amber-400 text-xs border-l-2 border-amber-600 pl-2 my-1">{line.replace(/^> ?/, '')}</p>
            }
            // Handle inline bold
            const parts = line.split(/(\*\*[^*]+\*\*)/)
            if (parts.length > 1) {
              return (
                <span key={i}>
                  {parts.map((part, j) =>
                    part.startsWith('**') ? (
                      <strong key={j} className="text-white font-semibold">
                        {part.replace(/\*\*/g, '')}
                      </strong>
                    ) : <span key={j}>{part}</span>
                  )}
                  <br />
                </span>
              )
            }
            return line ? <p key={i}>{line}</p> : <br key={i} />
          })}
        </div>
        {msg.tools_used && msg.tools_used.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {msg.tools_used.map(tool => (
              <span key={tool} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-polar-bg text-slate-600 border border-polar-border">
                <Wrench className="w-2.5 h-2.5" />
                {tool}
              </span>
            ))}
          </div>
        )}
        <div className="text-xs text-slate-600 px-1">
          {new Date(msg.timestamp).toLocaleTimeString()} ·
          {msg.llm_provider && <span className="ml-1">{msg.llm_provider}</span>}
        </div>
      </div>
    </div>
  )
}

export default function NavigatorPage() {
  const activeVessel = useActiveVessel()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Welcome to **Polar Navigator** — your AI-powered Antarctic navigation assistant.\n\nI can help you with:\n• Route recommendations and risk analysis\n• Sea ice conditions and forecasts\n• Iceberg tracking and trajectory prediction\n• Weather and ocean conditions\n• Vessel status and navigation decisions\n\nAsk me anything about current conditions or navigation!`,
      timestamp: new Date().toISOString(),
      llm_provider: 'rule_based',
    }
  ])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const mutation = useMutation({
    mutationFn: ({ query, context }: { query: string; context?: Record<string, any> }) =>
      queryAgent(query, context || {}),
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: data.response,
        tools_used: data.tools_used,
        llm_provider: data.llm_provider,
        timestamp: data.timestamp,
      }])
    },
  })

  const sendMessage = (text: string) => {
    if (!text.trim()) return
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }])
    // Include active vessel context
    const context: Record<string, any> = {}
    if (activeVessel) {
      context.active_vessel = {
        mmsi: activeVessel.mmsi,
        name: activeVessel.name,
        latitude: activeVessel.latitude,
        longitude: activeVessel.longitude,
        speed: activeVessel.speed,
        heading: activeVessel.heading,
        is_real: activeVessel.is_real,
      }
    }
    mutation.mutate({ query: text, context })
    setInput('')
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0">
        <PageHeader
          icon={Bot}
          title="Polar Navigator"
          subtitle="AI-powered Antarctic navigation assistant with real application data"
        />
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.map(msg => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {mutation.isPending && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-slate-700/50 border border-slate-600/30 flex items-center justify-center">
                  <Snowflake className="w-3.5 h-3.5 text-polar-accent" />
                </div>
                <div className="px-4 py-3 rounded-xl bg-polar-card border border-polar-border text-sm text-slate-400 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-polar-accent" />
                  Analyzing data and computing response...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-polar-border">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
                placeholder="Ask about routes, sea ice, icebergs, weather..."
                className="input-field flex-1"
                disabled={mutation.isPending}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={mutation.isPending || !input.trim()}
                className="btn-primary flex items-center gap-2"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Suggestions sidebar */}
        <div className="w-56 flex-shrink-0 border-l border-polar-border p-4 space-y-2 overflow-y-auto">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Suggested Queries</div>
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              onClick={() => sendMessage(s)}
              disabled={mutation.isPending}
              className="w-full text-left text-xs text-slate-400 hover:text-white p-2 rounded hover:bg-polar-border transition-colors leading-relaxed"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
