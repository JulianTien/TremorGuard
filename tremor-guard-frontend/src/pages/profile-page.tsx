import { Battery, ShieldAlert, Wifi } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useApiResource } from '../hooks/use-api-resource'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'
import { getProfile, unbindDevice } from '../lib/api'

export function ProfilePage() {
  const navigate = useNavigate()
  const { currentUser, refreshCurrentUser } = useAuth()
  const { data, error, isLoading } = useApiResource(getProfile, [])
  const hasBoundDevice = currentUser?.hasBoundDevice ?? false

  async function handleUnbindDevice() {
    await unbindDevice()
    const nextUser = await refreshCurrentUser()
    if (nextUser) {
      navigate(resolveAuthenticatedPath(nextUser), { replace: true })
    }
  }

  if (isLoading && !data) {
    return <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">正在加载个人档案...</div>
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        无法加载个人档案：{error ?? '未知错误'}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <div className="space-y-6 md:col-span-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 border-b border-slate-100 pb-4 text-base font-semibold text-slate-900">
            患者健康档案
          </h3>
          <div className="grid grid-cols-1 gap-x-4 gap-y-6 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-slate-400">姓名 (已脱敏处理)</p>
              <p className="text-sm font-medium text-slate-900">{data.patientProfile.name}</p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-400">年龄 / 性别</p>
              <p className="text-sm font-medium text-slate-900">
                {data.patientProfile.age}岁 / {data.patientProfile.gender}
              </p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-400">临床初步诊断</p>
              <p className="text-sm font-medium text-slate-900">{data.patientProfile.diagnosis}</p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-400">确诊时长</p>
              <p className="text-sm font-medium text-slate-900">{data.patientProfile.duration}</p>
            </div>
            <div className="md:col-span-2">
              <p className="mb-1 text-xs text-slate-400">主治医疗机构</p>
              <p className="text-sm font-medium text-slate-900">{data.patientProfile.hospital}</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 border-b border-slate-100 pb-4 text-base font-semibold text-slate-900">
            账号状态
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-slate-400">登录邮箱</p>
              <p className="text-sm font-medium text-slate-900">{currentUser?.email}</p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-400">当前状态</p>
              <p className="text-sm font-medium capitalize text-slate-900">{currentUser?.status}</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 flex items-center gap-2 border-b border-slate-100 pb-4 text-base font-semibold text-slate-900">
            <ShieldAlert className="h-4 w-4 text-slate-500" />
            数据隐私与安全设置
          </h3>
          <p className="mb-4 text-sm leading-relaxed text-slate-600">
            您的健康特征数据已在边缘端进行脱敏（匿名化）处理，使用国密标准 TLS 协议加密传输。系统严格遵循《个人信息保护法》(PIPL) 规范。
          </p>
          <div className="space-y-3">
            <label className="flex cursor-pointer items-center justify-between rounded-lg border border-slate-100 p-3 transition-colors hover:bg-slate-50">
              <span className="text-sm font-medium text-slate-700">允许向主治医生分享数据概览</span>
              <input type="checkbox" className="toggle-checkbox" checked={data.consentSettings.shareWithDoctor} readOnly />
            </label>
            <label className="flex cursor-pointer items-center justify-between rounded-lg border border-slate-100 p-3 transition-colors hover:bg-slate-50">
              <span className="text-sm font-medium text-slate-700">允许云端 RAG 知识库辅助分析病情</span>
              <input type="checkbox" className="toggle-checkbox" checked={data.consentSettings.ragAnalysisEnabled} readOnly />
            </label>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900 p-6 text-white shadow-sm">
          <div className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 rounded-full bg-slate-800 opacity-50" />
          <h3 className="mb-6 text-sm font-semibold text-slate-300">设备管理终端</h3>

          <div className="relative z-10 space-y-6">
            <div>
              <p className="mb-1 text-xs text-slate-400">绑定设备 S/N</p>
              <p className="font-mono text-sm tracking-wider">{data.patientProfile.deviceId}</p>
            </div>

            <div className="flex items-center gap-4 rounded-lg bg-slate-800 p-3">
              <Battery className="h-6 w-6 text-green-400" />
              <div>
                <p className="mb-0.5 text-xs text-slate-400">
                  剩余电量 ({data.deviceStatus.availableDays})
                </p>
                <div className="mt-1.5 h-1.5 w-32 rounded-full bg-slate-700">
                  <div
                    className="h-1.5 rounded-full bg-green-400"
                    style={{ width: `${data.deviceStatus.battery}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-lg bg-slate-800 p-3">
              <Wifi className="h-6 w-6 text-teal-400" />
              <div>
                <p className="mb-0.5 text-xs text-slate-400">边缘端同步状态</p>
                <p className="text-sm font-medium text-slate-200">{data.deviceStatus.connectionLabel}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleUnbindDevice}
              disabled={!hasBoundDevice}
              className="w-full rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              解绑当前手环
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
