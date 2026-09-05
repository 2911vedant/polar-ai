import { type LucideIcon } from 'lucide-react'
import DemoBanner from './DemoBanner'

interface PageHeaderProps {
  icon: LucideIcon
  title: string
  subtitle: string
  showDemoBanner?: boolean
  actions?: React.ReactNode
}

export default function PageHeader({ icon: Icon, title, subtitle, showDemoBanner = true, actions }: PageHeaderProps) {
  return (
    <div className="px-6 pt-6 pb-4 border-b border-polar-border">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-polar-accent/20 border border-polar-accent/30 flex items-center justify-center">
            <Icon className="w-5 h-5 text-polar-accent" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">{title}</h1>
            <p className="text-sm text-slate-500">{subtitle}</p>
          </div>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {showDemoBanner && <DemoBanner />}
    </div>
  )
}
