import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  message?: string
  size?: 'sm' | 'md' | 'lg'
}

export default function LoadingSpinner({ message = 'Loading...', size = 'md' }: LoadingSpinnerProps) {
  const iconSize = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : 'w-6 h-6'
  return (
    <div className="flex items-center justify-center gap-2 p-8 text-slate-500">
      <Loader2 className={`${iconSize} animate-spin text-polar-accent`} />
      <span className="text-sm">{message}</span>
    </div>
  )
}
