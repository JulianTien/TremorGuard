import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'
import { updateProfile } from '../lib/api'

export function OnboardingProfilePage() {
  const navigate = useNavigate()
  const { currentUser, refreshCurrentUser } = useAuth()
  const [form, setForm] = useState({
    name: currentUser?.displayName ?? '',
    age: 60,
    gender: '男',
    diagnosis: '帕金森病 (PD)',
    duration: '1年',
    hospital: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField<Key extends keyof typeof form>(key: Key, value: (typeof form)[Key]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await updateProfile(form)
      const user = await refreshCurrentUser()
      navigate(user ? resolveAuthenticatedPath(user) : '/onboarding/device-binding', { replace: true })
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : '资料保存失败，请稍后重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-3xl rounded-[32px] border border-slate-200 bg-white p-6 shadow-xl sm:p-10">
        <div className="mb-8">
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Step 1 of 2</p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-950">完善患者资料</h1>
          <p className="mt-2 text-sm text-slate-500">
            这些信息将用于后续展示个性化趋势说明，不会在注册阶段直接公开显示。
          </p>
        </div>

        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">姓名</span>
            <input
              required
              value={form.name}
              onChange={(event) => updateField('name', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">年龄</span>
            <input
              required
              min={18}
              max={120}
              type="number"
              value={form.age}
              onChange={(event) => updateField('age', Number(event.target.value))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">性别</span>
            <select
              value={form.gender}
              onChange={(event) => updateField('gender', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            >
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">确诊时长</span>
            <input
              required
              value={form.duration}
              onChange={(event) => updateField('duration', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
          </label>

          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">临床诊断</span>
            <input
              required
              value={form.diagnosis}
              onChange={(event) => updateField('diagnosis', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
          </label>

          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">主治医疗机构</span>
            <input
              required
              value={form.hospital}
              onChange={(event) => updateField('hospital', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
          </label>

          {error ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 md:col-span-2">
              {error}
            </div>
          ) : null}

          <div className="flex items-center justify-end md:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSubmitting ? '保存中...' : '保存并继续绑定'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
