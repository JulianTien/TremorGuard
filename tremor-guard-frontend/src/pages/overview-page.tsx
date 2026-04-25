import { Activity, ArrowRight, Battery, Clock, FileText, FolderOpenDot, MessageSquare, Pill, Stethoscope, Wifi } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { MetricTile } from '../components/ui/metric-tile'
import { TrendChart } from '../components/ui/trend-chart'
import { useApiResource } from '../hooks/use-api-resource'
import { DEFAULT_DATA_DATE, getOverview } from '../lib/api'

export function OverviewPage() {
  const { data, error, isLoading } = useApiResource(() => getOverview(DEFAULT_DATA_DATE), [])

  if (isLoading && !data) {
    return <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">正在加载总览数据...</div>
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        无法加载后端数据：{error ?? '未知错误'}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="监测总览"
        subtitle="这是患者侧日常管理首页，用于查看设备状态、监测波动、证据完备度，以及是否已具备 AI 解读与生成条件。"
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile metric={data.metricSummaries[0]} icon={Activity} />
        <MetricTile metric={data.metricSummaries[1]} icon={Activity} />
        <MetricTile metric={data.metricSummaries[2]} icon={Clock} />

        <div className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900 p-5 text-white shadow-sm">
          <div className="flex items-start justify-between">
            <span className="text-sm font-medium text-slate-300">设备状态</span>
            <Wifi className="h-5 w-5 text-teal-400" />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Battery className="h-4 w-4 text-green-400" />
              <span className="font-mono text-xl font-semibold">{data.deviceStatus.battery}%</span>
            </div>
            <p className="font-mono text-xs text-slate-400">{data.deviceStatus.lastSync}</p>
          </div>
        </div>
      </div>

      <div className="flex items-start gap-4 rounded-xl border border-teal-100 bg-teal-50 p-4">
        <div className="mt-0.5 shrink-0 rounded-lg bg-teal-600 p-2 text-white">
          <Stethoscope className="h-5 w-5" />
        </div>
        <div>
          <h4 className="mb-1 text-sm font-semibold text-slate-900">{data.overviewInsight.title}</h4>
          <p className="text-sm leading-relaxed text-slate-700">{data.overviewInsight.summary}</p>
        </div>
      </div>

      <SectionPanel
        title="证据完备度"
        description="系统根据今日监测、用药记录和病历档案状态，判断当前是否具备 AI 解读、康复计划生成和 AI 健康报告生成条件。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-3">
              <Pill className="h-5 w-5 text-teal-600" />
              <div>
                <p className="text-sm font-semibold text-slate-900">用药记录</p>
                <p className="text-xs text-slate-500">
                  {data.evidenceReadiness.hasMedicationLogs
                    ? `已记录 ${data.evidenceReadiness.medicationLogCount} 条`
                    : '今日尚未补充'}
                </p>
              </div>
            </div>
            <Link
              to="/medication"
              className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-teal-700 transition hover:text-teal-800"
            >
              前往用药记录
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-3">
              <FolderOpenDot className="h-5 w-5 text-teal-600" />
              <div>
                <p className="text-sm font-semibold text-slate-900">病历档案</p>
                <p className="text-xs text-slate-500">
                  {data.evidenceReadiness.hasMedicalRecordArchives
                    ? `已建立 ${data.evidenceReadiness.medicalRecordArchiveCount} 份档案`
                    : '尚未补充病历档案'}
                </p>
              </div>
            </div>
            <Link
              to="/records"
              className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-teal-700 transition hover:text-teal-800"
            >
              前往病历档案
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-3">
              <MessageSquare className="h-5 w-5 text-teal-600" />
              <div>
                <p className="text-sm font-semibold text-slate-900">AI 服务就绪度</p>
                <p className="text-xs text-slate-500">
                  解读 {data.evidenceReadiness.aiInterpretationReady ? '已就绪' : '待补充'} · 计划 {data.evidenceReadiness.rehabPlanReady ? '可生成' : '条件不足'} · 报告 {data.evidenceReadiness.healthReportReady ? '可生成' : '条件不足'}
                </p>
              </div>
            </div>
            <Link
              to="/ai-doctor"
              className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-teal-700 transition hover:text-teal-800"
            >
              前往 AI 医生
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
              监测事件 {data.evidenceReadiness.monitoringEventCount} 条
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
              设备绑定 {data.evidenceReadiness.hasDeviceBinding ? '已完成' : '未完成'}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.evidenceReadiness.nextSteps.map((step) => (
              <span
                key={step}
                className="rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800"
              >
                {step}
              </span>
            ))}
          </div>
        </div>
      </SectionPanel>

      <SectionPanel
        title="监测趋势"
        description="用监测波动和服药时间的关联视角观察今天的状态，便于后续交给 AI 医生解读或复诊沟通使用。"
      >
        <TrendChart points={data.trendPoints} />
      </SectionPanel>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Link
          to="/medication"
          className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-teal-200 hover:shadow-sm"
        >
          <div className="flex items-center gap-3">
            <Pill className="h-5 w-5 text-teal-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">补充用药记录</h3>
              <p className="mt-1 text-sm text-slate-500">完善药物与波动的行为证据。</p>
            </div>
          </div>
        </Link>

        <Link
          to="/records"
          className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-teal-200 hover:shadow-sm"
        >
          <div className="flex items-center gap-3">
            <FolderOpenDot className="h-5 w-5 text-teal-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">补充病历档案</h3>
              <p className="mt-1 text-sm text-slate-500">增强 AI 健康报告的证据质量。</p>
            </div>
          </div>
        </Link>

        <Link
          to="/reports"
          className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-teal-200 hover:shadow-sm"
        >
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-teal-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">查看 AI 健康报告</h3>
              <p className="mt-1 text-sm text-slate-500">统一进入患者侧结果输出中心。</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  )
}
