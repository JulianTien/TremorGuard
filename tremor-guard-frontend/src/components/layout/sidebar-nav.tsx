import {
  Activity,
  FileText,
  FolderOpenDot,
  MessageSquare,
  Pill,
  Sparkles,
  User,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../lib/auth-context'
import type { NavKey } from '../../types/domain'

interface NavItem {
  key: NavKey
  label: string
  path: string
  icon: LucideIcon
}

const navItems: NavItem[] = [
  { key: 'overview', label: '总览仪表盘', path: '/overview', icon: Activity },
  { key: 'ai-doctor', label: 'AI 医生', path: '/ai-doctor', icon: MessageSquare },
  { key: 'medication', label: '用药记录', path: '/medication', icon: Pill },
  { key: 'rehab-guidance', label: '康复训练计划', path: '/rehab-guidance', icon: Sparkles },
  { key: 'medical-records', label: '病历档案', path: '/records', icon: FolderOpenDot },
  { key: 'reports', label: '监测摘要报告', path: '/reports', icon: FileText },
  { key: 'profile', label: '个人中心', path: '/profile', icon: User },
]

export function SidebarNav() {
  const { currentUser } = useAuth()
  const deviceSerialLabel = currentUser?.boundDeviceSerial?.split('-').pop() ?? 'UNBOUND'

  return (
    <aside className="flex h-full flex-col overflow-hidden rounded-[24px] bg-slate-900 text-slate-300">
      <div className="flex items-center border-b border-slate-800 bg-slate-950 px-6 py-5">
        <Activity className="mr-3 h-6 w-6 text-teal-500" />
        <div>
          <h1 className="text-lg font-bold leading-tight tracking-wide text-white">震颤卫士</h1>
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate-500">
            Tremor Guard
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-6">
        {navItems.map((item) => {
          const Icon = item.icon

          return (
            <NavLink
              key={item.key}
              to={item.path}
              className={({ isActive }) =>
                [
                  'relative flex items-center rounded-lg px-3 py-3 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  {isActive ? (
                    <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-md bg-teal-500" />
                  ) : null}
                  <Icon className={`mr-3 h-5 w-5 ${isActive ? 'text-teal-400' : 'opacity-70'}`} />
                  {item.label}
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      <div className="border-t border-slate-800 p-4">
        <div className="flex items-center gap-3 rounded-lg border border-slate-700/50 bg-slate-800/50 p-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-slate-300">
            {currentUser?.displayName?.[0] ?? '患'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{currentUser?.displayName ?? '患者账号'}</p>
            <p className="truncate text-[10px] text-slate-400">
              S/N: {deviceSerialLabel}
            </p>
          </div>
        </div>
      </div>
    </aside>
  )
}
