import type {
  AiInsight,
  ChatMessage,
  DeviceStatus,
  MedicationEntry,
  PatientProfile,
  ReportSummary,
  TremorMetricSummary,
  TremorTrendPoint,
} from '../types/domain'

export const patientProfile: PatientProfile = {
  id: 'TG-CN-001',
  name: '张建国',
  age: 68,
  gender: '男',
  diagnosis: '帕金森病 (PD)',
  duration: '3年',
  hospital: '上海市第一人民医院',
  deviceId: 'TG-V1.0-ESP-8A92',
}

export const deviceStatus: DeviceStatus = {
  battery: 82,
  connection: 'stable',
  connectionLabel: '已连接 · 实时监测中',
  lastSync: '14:22 最后同步',
  availableDays: '预计可用 5 天',
  firmware: 'v1.0.6',
}

export const metricSummaries: TremorMetricSummary[] = [
  {
    label: '今日发作频次',
    value: 12,
    unit: '次',
    subtitle: '较昨日 +15%',
    tone: 'alert',
  },
  {
    label: '平均主频率',
    value: 4.8,
    unit: 'Hz',
    subtitle: '典型PD频段: 4-6Hz',
    tone: 'neutral',
  },
  {
    label: '平均持续时长',
    value: 45,
    unit: '秒',
    subtitle: '最长: 112秒',
    tone: 'neutral',
  },
]

export const overviewInsight: AiInsight = {
  id: 'ai-overview-1',
  title: 'AI 医生摘要洞察',
  summary:
    '今日上午 10:00 及下午 15:00 左右出现两次较为密集的震颤波峰。结合您的服药时间（08:00, 13:00），这两个时段可能处于药效“剂末阶段”。建议您在下次复诊时向医生展示此图表，探讨是否需要微调给药间隔。',
}

export const aiInsights: AiInsight[] = [
  {
    id: 'ai-note-1',
    title: '药后观察重点',
    summary: '建议优先关注服药后 30 分钟、90 分钟和 3 小时三个时间窗口。',
    emphasis: '这些节点最容易帮助医生辨认“起效”与“剂末”变化。',
  },
  {
    id: 'ai-note-2',
    title: '午后波动说明',
    summary: '若午后高峰连续出现，价值在于形成趋势，而不是单次判断病情轻重。',
    emphasis: '系统只做辅助解读，不提供诊断和处方建议。',
  },
]

export const trendPoints: TremorTrendPoint[] = [
  { time: '00:00', amplitude: 0.2 },
  { time: '02:00', amplitude: 0.25 },
  { time: '04:00', amplitude: 0.15 },
  { time: '06:00', amplitude: 0.4 },
  { time: '08:00', amplitude: 0.62, medicationTaken: true, label: '08:00 服药' },
  { time: '10:00', amplitude: 0.35 },
  { time: '12:00', amplitude: 0.3 },
  { time: '13:00', amplitude: 0.28, medicationTaken: true, label: '13:00 服药' },
  { time: '15:00', amplitude: 0.72 },
  { time: '18:00', amplitude: 0.42 },
  { time: '21:00', amplitude: 0.32 },
  { time: '24:00', amplitude: 0.22 },
]

export const chatMessages: ChatMessage[] = [
  {
    id: 1,
    role: 'assistant',
    content:
      '您好，张先生。我是您的专属健康助手“震颤卫士”。根据您今天上午的数据，我注意到 10:00 左右有一次较明显的震颤波动。请问您现在感觉怎么样？',
  },
  {
    id: 2,
    role: 'user',
    content: '我现在感觉手有点僵，而且抖得比早上厉害。',
  },
  {
    id: 3,
    role: 'assistant',
    content:
      '根据您的监测数据分析，您目前的震颤频率约为 4.8Hz，属于帕金森震颤的典型范围。结合您的服药记录，现在可能接近您上一次服药后的“药效低谷期”（剂末现象）。建议您先坐下休息，避免紧张情绪。如果这种不适感在下午 1 点服药后仍未缓解，建议记录下来在复诊时告知主治医生。\n\n⚠️ 提示：以上数据分析与建议仅供健康管理参考，不构成任何医疗诊断意见。如有疑问或严重不适，请务必咨询您的专业医生。',
  },
]

export const quickQuestions = [
  '帮我分析今天的数据波动',
  '为什么下午手抖突然加重了？',
  '左旋多巴类药物有哪些副作用？',
  '适合帕金森的居家康复运动',
]

export const medicationEntries: MedicationEntry[] = [
  { id: 1, time: '08:00', name: '多巴丝肼片 (美多芭)', dose: '125mg', status: 'taken' },
  { id: 2, time: '13:00', name: '多巴丝肼片 (美多芭)', dose: '125mg', status: 'taken' },
  { id: 3, time: '18:00', name: '多巴丝肼片 (美多芭)', dose: '125mg', status: 'pending' },
]

export const reports: ReportSummary[] = [
  { id: 'R-20260405', date: '2026-04-05', type: '周度病情评估摘要', size: '1.2 MB' },
  { id: 'R-20260329', date: '2026-03-29', type: '周度病情评估摘要', size: '1.1 MB' },
  { id: 'R-20260301', date: '2026-03-01', type: '月度长程震颤趋势报告', size: '3.4 MB' },
]
