import { Activity } from 'lucide-react'
import { Show, SignInButton, SignUpButton } from '@clerk/react'
import { useAuth } from '../lib/auth-context'

export function LoginPage() {
  const { authError, logout } = useAuth()

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(13,148,136,0.18),_transparent_28%),linear-gradient(180deg,_#f8fafc_0%,_#e2e8f0_100%)] px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[32px] border border-white/60 bg-white/90 shadow-[0_30px_80px_rgba(15,23,42,0.12)] backdrop-blur md:grid-cols-[1.1fr_0.9fr]">
        <section className="hidden flex-col justify-between bg-slate-950 px-10 py-12 text-white md:flex">
          <div>
            <div className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              <Activity className="h-4 w-4 text-teal-400" />
              TremorGuard Patient Access
            </div>
            <h1 className="max-w-md text-4xl font-semibold leading-tight">
              登录后继续查看震颤趋势、用药记录与设备状态。
            </h1>
            <p className="mt-5 max-w-md text-sm leading-7 text-slate-300">
              一期用户体系以患者自助使用为核心。首次注册后会先完成资料补全，再绑定手环进入工作台。
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">
            <p className="font-medium text-white">账号入口</p>
            <p className="mt-2 leading-6">
              登录完成后系统会自动建立 TremorGuard 工作台会话，并继续执行资料补全与设备绑定流程。
            </p>
          </div>
        </section>

        <section className="px-6 py-8 sm:px-10 sm:py-12">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-8 md:hidden">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-700">
                <Activity className="h-3.5 w-3.5" />
                TremorGuard
              </div>
              <h1 className="text-3xl font-semibold text-slate-950">患者登录</h1>
            </div>

            <div className="mb-8 hidden md:block">
              <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Patient Sign In</p>
              <h2 className="mt-3 text-3xl font-semibold text-slate-950">欢迎回来</h2>
              <p className="mt-2 text-sm text-slate-500">使用 Clerk 账号恢复您的监测会话。</p>
            </div>

            <Show when="signed-out">
              <div className="space-y-3">
                <SignInButton mode="redirect" forceRedirectUrl="/login">
                  <button
                    type="button"
                    className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
                  >
                    登录
                  </button>
                </SignInButton>
                <SignUpButton mode="redirect" forceRedirectUrl="/onboarding/profile">
                  <button
                    type="button"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700"
                  >
                    创建新账号
                  </button>
                </SignUpButton>
              </div>
            </Show>

            <Show when="signed-in">
              <div className="space-y-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-800">
                <p className="font-medium text-amber-900">Clerk 已登录，正在建立工作台会话。</p>
                {authError ? <p>{authError}</p> : null}
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="rounded-full bg-slate-950 px-3 py-1.5 text-xs font-medium text-white"
                  >
                    重试
                  </button>
                  <button
                    type="button"
                    onClick={() => void logout()}
                    className="rounded-full border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800"
                  >
                    退出 Clerk 后重新登录
                  </button>
                </div>
              </div>
            </Show>

            <p className="mt-6 text-sm text-slate-500">
              还没有账号？
              <SignUpButton mode="redirect" forceRedirectUrl="/onboarding/profile">
                <button type="button" className="ml-1 font-medium text-teal-700 hover:text-teal-600">
                  立即注册
                </button>
              </SignUpButton>
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
