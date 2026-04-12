import { Activity } from 'lucide-react'
import type { TremorTrendPoint } from '../../types/domain'

interface TrendChartProps {
  points: TremorTrendPoint[]
}

export function TrendChart({ points }: TrendChartProps) {
  const plotPoints = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100
      const y = 100 - point.amplitude * 100

      return `${x},${y}`
    })
    .join(' ')

  const areaPoints = `0,100 ${plotPoints} 100,100`

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h3 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <Activity className="h-4 w-4 text-teal-600" />
          24小时震颤幅度与频次趋势
        </h3>
        <div className="flex gap-4 text-xs text-slate-600">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-teal-500" />
            震颤幅度 (RMS)
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-amber-400" />
            用药锚点
          </div>
        </div>
      </div>

      <div className="relative min-h-[18rem] flex-1 border-b border-l border-slate-200">
        <div className="absolute -left-8 top-0 bottom-0 flex flex-col justify-between py-2 font-mono text-[10px] text-slate-400">
          <span>0.8</span>
          <span>0.6</span>
          <span>0.4</span>
          <span>0.2</span>
          <span>0.0</span>
        </div>
        <div className="absolute -bottom-6 left-0 right-0 flex justify-between px-2 font-mono text-[10px] text-slate-400">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>

        <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 100 100">
          <line x1="0" y1="25" x2="100" y2="25" stroke="#f1f5f9" strokeWidth="0.5" />
          <line x1="0" y1="50" x2="100" y2="50" stroke="#f1f5f9" strokeWidth="0.5" />
          <line x1="0" y1="75" x2="100" y2="75" stroke="#f1f5f9" strokeWidth="0.5" />
          <polyline
            points={plotPoints}
            fill="none"
            stroke="#0d9488"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <polygon points={areaPoints} fill="url(#teal-gradient)" opacity="0.12" />
          <defs>
            <linearGradient id="teal-gradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#0d9488" />
              <stop offset="100%" stopColor="#ffffff" />
            </linearGradient>
          </defs>
          {points.map((point, index) => {
            if (!point.medicationTaken) {
              return null
            }

            const x = (index / Math.max(points.length - 1, 1)) * 100
            const y = 100 - point.amplitude * 100

            return (
              <g key={point.time}>
                <line
                  x1={x}
                  y1="0"
                  x2={x}
                  y2="100"
                  stroke="#fbbf24"
                  strokeWidth="1"
                  strokeDasharray="2,2"
                />
                <rect x={x - 2} y={y - 2} width="4" height="4" fill="#fbbf24" rx="1" />
                {point.label ? (
                  <text x={Math.min(x + 2, 88)} y="10" fontSize="3" fill="#fbbf24">
                    {point.label}
                  </text>
                ) : null}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
