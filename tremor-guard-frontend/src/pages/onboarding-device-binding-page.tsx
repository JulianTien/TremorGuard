import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'
import { bindDemoDevice, bindDevice, getDeviceBinding } from '../lib/api'

const DEMO_DEVICE_SERIAL = import.meta.env.VITE_DEMO_DEVICE_SERIAL ?? 'TG-V1.0-ESP-7B31'
const DEMO_ACTIVATION_CODE = import.meta.env.VITE_DEMO_DEVICE_ACTIVATION_CODE ?? 'TG-ACT-7B31'

export function OnboardingDeviceBindingPage() {
  const navigate = useNavigate()
  const { refreshCurrentUser } = useAuth()
  const [deviceSerial, setDeviceSerial] = useState(DEMO_DEVICE_SERIAL)
  const [activationCode, setActivationCode] = useState(DEMO_ACTIVATION_CODE)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoadingCurrent, setIsLoadingCurrent] = useState(false)
  const [isBindingDemo, setIsBindingDemo] = useState(false)
  const [currentBindingLabel, setCurrentBindingLabel] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await bindDevice({ deviceSerial, activationCode })
      const user = await refreshCurrentUser()
      navigate(user ? resolveAuthenticatedPath(user) : '/overview', { replace: true })
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : '设备绑定失败，请稍后重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleRefreshBinding() {
    setIsLoadingCurrent(true)
    setError(null)

    try {
      const result = await getDeviceBinding()
      if (result.completion.onboardingState === 'active') {
        const user = await refreshCurrentUser()
        navigate(user ? resolveAuthenticatedPath(user) : '/overview', { replace: true })
        return
      }

      setCurrentBindingLabel(
        result.deviceBinding
          ? `${result.deviceBinding.deviceName} · ${result.deviceBinding.deviceSerial}`
          : '当前尚未绑定设备',
      )
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '无法读取设备状态。')
    } finally {
      setIsLoadingCurrent(false)
    }
  }

  async function handleBindDemoDevice() {
    setIsBindingDemo(true)
    setError(null)

    try {
      await bindDemoDevice()
      const user = await refreshCurrentUser()
      navigate(user ? resolveAuthenticatedPath(user) : '/overview', { replace: true })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '无法完成演示设备绑定。')
    } finally {
      setIsBindingDemo(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-xl md:grid-cols-[1.05fr_0.95fr]">
        <section className="bg-slate-950 px-8 py-10 text-white">
          <p className="text-sm uppercase tracking-[0.28em] text-slate-500">Step 2 of 2</p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight">绑定手环后即可进入患者工作台。</h1>
          <p className="mt-4 text-sm leading-7 text-slate-300">
            一期采用“一人一台有效设备”规则。若当前账号已有绑定设备，绑定新设备后旧设备会自动失效。
          </p>

          <button
            type="button"
            onClick={() => {
              navigate('/onboarding/profile')
            }}
            className="mt-6 rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/5"
          >
            返回修改患者资料
          </button>

          <div className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm font-medium text-white">本地演示可用设备</p>
            <p className="mt-3 font-mono text-sm text-slate-300">S/N: {DEMO_DEVICE_SERIAL}</p>
            <p className="mt-1 font-mono text-sm text-slate-300">Activation: {DEMO_ACTIVATION_CODE}</p>
          </div>

          <button
            type="button"
            onClick={handleRefreshBinding}
            className="mt-5 rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/5"
          >
            {isLoadingCurrent ? '读取中...' : '查看当前绑定状态'}
          </button>

          <button
            type="button"
            onClick={handleBindDemoDevice}
            disabled={isBindingDemo}
            className="mt-3 rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isBindingDemo ? '绑定中...' : '使用演示设备快速体验'}
          </button>

          {currentBindingLabel ? <p className="mt-4 text-sm text-slate-300">{currentBindingLabel}</p> : null}
        </section>

        <section className="px-6 py-8 sm:px-10 sm:py-10">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-slate-950">录入设备信息</h2>
            <p className="mt-2 text-sm text-slate-500">请输入手环包装或设备卡片上的序列号与激活码。</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">设备序列号</span>
              <input
                required
                value={deviceSerial}
                onChange={(event) => setDeviceSerial(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm outline-none transition focus:border-teal-500 focus:bg-white"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">激活码</span>
              <input
                required
                value={activationCode}
                onChange={(event) => setActivationCode(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm outline-none transition focus:border-teal-500 focus:bg-white"
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
              {isSubmitting ? '绑定中...' : '绑定设备并进入工作台'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
