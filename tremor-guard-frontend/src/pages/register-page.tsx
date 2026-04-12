import { Activity } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'

export function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const user = await register(email, password, displayName)
      navigate(resolveAuthenticatedPath(user), { replace: true })
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : '注册失败，请稍后重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.14),_transparent_30%),linear-gradient(180deg,_#f8fafc_0%,_#e2e8f0_100%)] px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[32px] border border-white/60 bg-white/90 shadow-[0_30px_80px_rgba(15,23,42,0.12)] backdrop-blur md:grid-cols-[0.95fr_1.05fr]">
        <section className="px-6 py-8 sm:px-10 sm:py-12">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-8">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-700">
                <Activity className="h-3.5 w-3.5" />
                TremorGuard
              </div>
              <h1 className="text-3xl font-semibold text-slate-950">创建患者账号</h1>
              <p className="mt-2 text-sm text-slate-500">
                注册后会立即进入资料补全与设备绑定流程。
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">显示姓名</span>
                <input
                  required
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white"
                />
              </label>

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
                  minLength={8}
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
                {isSubmitting ? '创建中...' : '注册并继续'}
              </button>
            </form>

            <p className="mt-6 text-sm text-slate-500">
              已有账号？
              <Link to="/login" className="ml-1 font-medium text-teal-700 hover:text-teal-600">
                返回登录
              </Link>
            </p>
          </div>
        </section>

        <section className="hidden flex-col justify-between bg-slate-950 px-10 py-12 text-white md:flex">
          <div>
            <p className="text-sm uppercase tracking-[0.28em] text-slate-500">Onboarding</p>
            <h2 className="mt-4 text-4xl font-semibold leading-tight">
              先建账号，再补资料，最后绑定手环。
            </h2>
          </div>

          <div className="space-y-4">
            {[
              '1. 注册仅保存基础身份信息，不在此阶段填写医疗资料。',
              '2. 首次登录后补全年龄、性别、诊断与医院信息。',
              '3. 用设备序列号和激活码完成唯一绑定后进入工作台。',
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                {item}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
