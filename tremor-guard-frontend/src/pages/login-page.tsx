import { Activity } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('patient@tremorguard.local')
  const [password, setPassword] = useState('tg-demo-password')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const user = await login(email, password)
      navigate(resolveAuthenticatedPath(user), { replace: true })
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : '登录失败，请稍后重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

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
            <p className="font-medium text-white">演示账号</p>
            <p className="mt-2">邮箱: patient@tremorguard.local</p>
            <p>密码: tg-demo-password</p>
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
              <p className="mt-2 text-sm text-slate-500">使用邮箱与密码恢复您的监测会话。</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">邮箱</span>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">密码</span>
                <input
                  required
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white"
                />
              </label>

              {error ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {isSubmitting ? '登录中...' : '登录'}
              </button>
            </form>

            <p className="mt-6 text-sm text-slate-500">
              还没有账号？
              <Link to="/register" className="ml-1 font-medium text-teal-700 hover:text-teal-600">
                立即注册
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
