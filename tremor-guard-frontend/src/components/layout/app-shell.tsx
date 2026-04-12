import { Outlet } from 'react-router-dom'
import { ComplianceBanner } from '../ui/compliance-banner'
import { SidebarNav } from './sidebar-nav'
import { TopBar } from './top-bar'

export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="flex min-h-screen flex-col lg:flex-row">
        <div className="w-full shrink-0 lg:h-screen lg:w-64">
          <SidebarNav />
        </div>

        <div className="flex min-w-0 flex-1 flex-col bg-slate-50">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-4 md:p-8">
            <div className="mx-auto w-full max-w-6xl">
              <Outlet />
            </div>
          </main>
          <ComplianceBanner />
        </div>
      </div>
    </div>
  )
}
