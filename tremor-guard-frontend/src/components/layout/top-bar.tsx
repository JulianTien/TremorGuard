import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../lib/auth-context'

function resolvePageTitle(pathname: string) {
  if (pathname.startsWith('/records/reports/')) {
    return '病历联合健康报告'
  }

  if (pathname.startsWith('/records/')) {
    return '病历档案详情'
  }

  if (pathname === '/records') {
    return '病历档案'
  }

  if (pathname === '/overview') {
    return '总览仪表盘'
  }

  if (pathname === '/ai-doctor') {
    return 'AI 医生'
  }

  if (pathname === '/medication') {
    return '用药记录'
  }

  if (pathname === '/rehab-guidance') {
    return '个性化训练计划'
  }

  if (pathname === '/reports') {
    return '监测摘要报告'
  }

  if (pathname === '/profile') {
    return '个人中心'
  }

  return '患者工作台'
}

export function TopBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentUser, logout } = useAuth()
  const pageTitle = resolvePageTitle(location.pathname)
  const realtime = location.pathname === '/overview'

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-slate-900">{pageTitle}</h2>
        {realtime ? (
          <span className="ml-2 rounded border border-teal-100 bg-teal-50 px-2 py-0.5 text-[10px] font-medium text-teal-700">
            实时监测中
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-1.5 font-mono text-xs text-slate-500 md:flex">
          <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
          设备在线
        </div>

        <div className="hidden rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500 md:block">
          {currentUser?.displayName ?? '患者账号'}
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
        >
          退出登录
        </button>
      </div>
    </header>
  )
}
