import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { resolveAuthenticatedPath, useAuth } from '../lib/auth-context'
import { getProfile, updateProfile } from '../lib/api'

const DURATION_OPTIONS = ['新近确诊', '半年以内', '6个月-1年', '1年', '1-3年', '3-5年', '5-10年', '10年以上']
const OTHER_DIAGNOSIS_OPTION = '其他'
const DIAGNOSIS_OPTIONS = [
  '帕金森病 (PD)',
  '原发性震颤',
  '帕金森综合征',
  '药物诱发性帕金森综合征',
  '多系统萎缩 (MSA)',
  '进行性核上性麻痹 (PSP)',
  '路易体痴呆相关帕金森症状',
  '血管性帕金森综合征',
]

function parseDiagnosisValue(value: string) {
  const parts = value
    .split(/[、，,;；/]/)
    .map((part) => part.trim())
    .filter(Boolean)
  const selected = parts.filter((part) => DIAGNOSIS_OPTIONS.includes(part))
  const otherParts = parts
    .filter((part) => !DIAGNOSIS_OPTIONS.includes(part))
    .map((part) => part.replace(/^其他[:：]\s*/, '').trim())
    .filter(Boolean)

  return {
    selectedDiagnoses: selected.length > 0 ? selected : ['帕金森病 (PD)'],
    otherDiagnosis: otherParts.join('、'),
  }
}

function buildDiagnosisValue(selectedDiagnoses: string[], otherDiagnosis: string) {
  const selectedCommonDiagnoses = selectedDiagnoses.filter((diagnosis) => diagnosis !== OTHER_DIAGNOSIS_OPTION)
  const trimmedOtherDiagnosis = otherDiagnosis.trim()

  return [
    ...selectedCommonDiagnoses,
    trimmedOtherDiagnosis ? `其他：${trimmedOtherDiagnosis}` : '',
  ]
    .filter(Boolean)
    .join('、')
}

export function OnboardingProfilePage() {
  const navigate = useNavigate()
  const { currentUser, refreshCurrentUser } = useAuth()
  const [form, setForm] = useState({
    name: currentUser?.displayName ?? '',
    age: 60,
    gender: '男',
    duration: '1年',
    hospital: '',
  })
  const [selectedDiagnoses, setSelectedDiagnoses] = useState<string[]>(['帕金森病 (PD)'])
  const [otherDiagnosis, setOtherDiagnosis] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoadingProfile, setIsLoadingProfile] = useState(false)
  const diagnosisValue = buildDiagnosisValue(selectedDiagnoses, otherDiagnosis)
  const diagnosisSummary = diagnosisValue || '请选择一个或多个临床诊断'

  useEffect(() => {
    let cancelled = false

    async function loadExistingProfile() {
      if (currentUser?.onboardingState !== 'device_binding_required') {
        return
      }

      setIsLoadingProfile(true)
      try {
        const result = await getProfile()
        if (cancelled) {
          return
        }

        const { patientProfile } = result
        setForm({
          name: patientProfile.name,
          age: patientProfile.age,
          gender: patientProfile.gender,
          duration: patientProfile.duration,
          hospital: patientProfile.hospital,
        })

        const parsedDiagnosis = parseDiagnosisValue(patientProfile.diagnosis)
        setSelectedDiagnoses([
          ...parsedDiagnosis.selectedDiagnoses,
          ...(parsedDiagnosis.otherDiagnosis ? [OTHER_DIAGNOSIS_OPTION] : []),
        ])
        setOtherDiagnosis(parsedDiagnosis.otherDiagnosis)
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : '无法读取已保存的患者资料。')
        }
      } finally {
        if (!cancelled) {
          setIsLoadingProfile(false)
        }
      }
    }

    void loadExistingProfile()

    return () => {
      cancelled = true
    }
  }, [currentUser?.onboardingState])

  function updateField<Key extends keyof typeof form>(key: Key, value: (typeof form)[Key]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleDiagnosis(diagnosis: string) {
    setSelectedDiagnoses((current) => {
      if (current.includes(diagnosis)) {
        return current.filter((item) => item !== diagnosis)
      }

      return [...current, diagnosis]
    })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      if (!diagnosisValue) {
        setError('请至少选择或填写一个临床诊断。')
        return
      }

      await updateProfile({
        ...form,
        diagnosis: diagnosisValue,
      })
      const user = await refreshCurrentUser()
      navigate(user ? resolveAuthenticatedPath(user) : '/onboarding/device-binding')
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
          {isLoadingProfile ? <p className="mt-3 text-sm text-teal-700">正在载入已保存资料...</p> : null}
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
              list="diagnosis-duration-options"
              value={form.duration}
              onChange={(event) => updateField('duration', event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
            />
            <datalist id="diagnosis-duration-options">
              {DURATION_OPTIONS.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </label>

          <div className="block md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">临床诊断</span>
            <details className="group relative">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none transition hover:bg-white focus:border-teal-500 focus:bg-white">
                <span>{diagnosisSummary}</span>
                <span className="text-xs text-slate-400 group-open:rotate-180">▼</span>
              </summary>
              <div className="absolute z-20 mt-2 w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
                <div className="grid gap-2 md:grid-cols-2">
                  {DIAGNOSIS_OPTIONS.map((option) => (
                    <label
                      key={option}
                      className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={selectedDiagnoses.includes(option)}
                        onChange={() => toggleDiagnosis(option)}
                        className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                      />
                      <span>{option}</span>
                    </label>
                  ))}
                  <label className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={selectedDiagnoses.includes(OTHER_DIAGNOSIS_OPTION)}
                      onChange={() => toggleDiagnosis(OTHER_DIAGNOSIS_OPTION)}
                      className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                    <span>其他</span>
                  </label>
                </div>
                {selectedDiagnoses.includes(OTHER_DIAGNOSIS_OPTION) ? (
                  <input
                    value={otherDiagnosis}
                    onChange={(event) => setOtherDiagnosis(event.target.value)}
                    placeholder="请输入其他临床诊断"
                    className="mt-3 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-teal-500 focus:bg-white"
                  />
                ) : null}
              </div>
            </details>
            <p className="mt-2 text-xs text-slate-500">可多选；如不在列表中，请选择“其他”并补充填写。</p>
          </div>

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
