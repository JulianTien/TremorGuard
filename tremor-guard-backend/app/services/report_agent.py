from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
import json
from statistics import mean
from string import Template

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.clinical import (
    LongitudinalReport,
    MedicationLog,
    MedicalRecordArchive,
    MedicalRecordExtraction,
    PatientProfile,
    TremorEvent,
)
from app.models.identity import User
from app.services.dashscope_client import post_chat_completion
from app.services.dashboard import format_device_status, get_latest_device_status

REPORT_AGENT_SYSTEM_PROMPT = """你是一名用于帕金森病健康管理场景的医疗报告生成助手。你的任务是根据患者的可穿戴设备监测数据、用药记录、病史摘要和问卷信息，生成一份“帕金森患者健康分析报告”。

你的角色不是做临床确诊，也不是替代医生下治疗结论。你必须严格遵守以下规则：

1. 报告用途
- 报告仅用于辅助健康管理、复诊准备和医患沟通。
- 不得将报告写成确诊书、分期结论书或处方建议书。
- 不得声称“明确提示病情加重”“明确需要调整药物”，除非输入明确提供医生结论。

2. 写作目标
- 报告应完整、正式、具体，有医学分析感，但语气克制。
- 即使数据不足，也要进行“有限分析”。
- 不允许只重复原始数据，必须把数据转化为观察、解释、限制和建议。
- 报告篇幅应明显高于简单摘要，每个核心章节至少输出2到5句分析性内容；如果数据极少，也要说明限制和下一步建议。

3. 推理边界
- 只能基于输入数据做结论。
- 不得虚构不存在的症状、检查结果、量表评分、既往史、家族史、生活能力受损情况。
- 对于缺失信息，要明确写“当前未提供”或“尚无法判断”，并说明这会影响什么判断。
- 如果仅有震颤数据，只能重点分析震颤维度，不能把它扩大解释成完整运动功能评估。

4. 报告风格
- 使用中文专业书面表达。
- 风格接近神经内科/慢病管理随访报告。
- 先总结，再展开；先事实，再分析；先能判断的，再写限制。
- 避免口语化、营销化、夸张化表达。
- 不要频繁重复“数据不足/待补充”这句空话，而要写明“缺什么，因此不能判断什么”。

5. 固定输出逻辑
对于每个章节，尽可能按以下顺序组织：
- 本章节已知事实
- 基于事实可做的观察
- 当前不能判断的内容
- 对复诊/管理的意义

6. 必须包含的安全表述
- 报告用于辅助健康管理与复诊沟通，不替代医生诊断。
- 本报告不能单独用于疾病分期、疗效最终判断或治疗方案制定。
- 建议结合专科面诊、查体、量表和既往病历综合评估。

7. 输出要求
- 输出完整正式报告，不输出提示词解释，不输出思维过程。
- 可以使用 Markdown 表格、引用块、二级小标题和可执行清单来提升可读性。
- 不要省略章节；章节标题必须与用户要求一致。
- 如果某章节无数据，也要说明该项评估的临床意义、缺失资料会限制什么判断，以及建议补充什么资料，而不是只写“无”或“待补充”。"""

REPORT_AGENT_USER_TEMPLATE = Template(
    """请根据以下患者资料，生成一份详细的《帕金森患者健康分析报告》。

要求：
- 必须严格基于输入数据生成，不得编造。
- 报告应详细、正式、可读，适合用于复诊前准备和健康管理归档。
- 每个章节都要有分析性表述，不能只罗列数据。
- 如果信息不足，请明确说明“缺少什么，因此不能判断什么”，并给出后续补充建议。
- 报告中要体现“症状监测数据、用药记录、风险提示、局限性、随访建议”。
- 禁止输出疾病分期结论，除非输入中明确提供量表或医生结论。
- 禁止输出确定性治疗调整建议，可写“建议结合专科医生评估”。

患者资料如下：

[基本信息]
姓名：$name
年龄：$age
性别：$gender
诊断背景：$diagnosis_background

[报告背景]
报告用途：$report_purpose
监测时间范围：$monitoring_window

[监测数据]
震颤事件总数：$tremor_event_count
平均幅度：$tremor_avg_amplitude
峰值幅度：$tremor_peak_amplitude
是否有时间分布信息：$has_time_distribution
时间分布摘要：$time_distribution_summary
是否有趋势信息：$has_trend
趋势摘要：$trend_summary

[用药记录]
$medication_records

[系统已计算的分析摘要]
$analytics_summary_text

[用药-症状关联摘要]
$medication_correlation_summary

[历史基线对比]
$baseline_summary

[数据补充建议]
$data_completion_guidance

[复诊准备清单]
$followup_checklist

[症状自评问卷]
$self_assessment_questions

[知识科普卡片]
$knowledge_cards

[参考性健康管理提示]
$clinical_reference_notes

[既往史]
$past_history

[家族史]
$family_history

[生活方式]
$lifestyle

[非运动症状]
$non_motor_symptoms

[日常生活能力]
$adl_info

[体格检查]
$physical_exam

[辅助检查]
$tests_and_imaging

[量表]
$scales

[补充上下文]
生成触发原因：$trigger_reason
补充关注点：$supplemental_focus

请按以下结构输出：
1. 基本信息
2. 评估目的
3. 本次监测亮点与异常提示
4. 主诉与现病史
5. 既往史、家族史及生活方式
6. 当前治疗与用药情况
7. 用药-症状关联分析
8. 运动症状评估
9. 非运动症状评估
10. 日常生活能力评估
11. 体格检查
12. 辅助检查结果
13. 量表评分与疾病分期
14. 主要健康问题总结
15. 综合分析
16. 干预建议
17. 复诊准备清单
18. 症状自评问卷
19. 知识科普卡片
20. 随访计划
21. 结论"""
)

REPORT_TEMPLATE_SECTIONS = [
    "1. 基本信息",
    "2. 评估目的",
    "3. 本次监测亮点与异常提示",
    "4. 主诉与现病史",
    "5. 既往史、家族史及生活方式",
    "6. 当前治疗与用药情况",
    "7. 用药-症状关联分析",
    "8. 运动症状评估",
    "9. 非运动症状评估",
    "10. 日常生活能力评估",
    "11. 体格检查",
    "12. 辅助检查结果",
    "13. 量表评分与疾病分期",
    "14. 主要健康问题总结",
    "15. 综合分析",
    "16. 干预建议",
    "17. 复诊准备清单",
    "18. 症状自评问卷",
    "19. 知识科普卡片",
    "20. 随访计划",
    "21. 结论",
]


def _stringify_lines(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    return "\n".join(f"- {value}" for value in cleaned) if cleaned else "当前未提供。"


def _event_time_distribution_summary(events: list[TremorEvent]) -> tuple[str, str]:
    if not events:
        return "否", "当前未提供时间分布信息，因此无法判断日内波动特点。"

    hourly_counter = Counter(event.start_at.hour for event in events)
    busiest_hours = sorted(hourly_counter.items(), key=lambda item: (-item[1], item[0]))[:3]
    summary = "；".join(f"{hour:02d}:00 附近记录 {count} 次事件" for hour, count in busiest_hours)
    return "是", summary or "已有事件记录，但当前无法归纳明确的时间分布特点。"


def _trend_summary(events: list[TremorEvent]) -> tuple[str, str]:
    if len(events) < 2:
        return "否", "当前事件数量不足，难以形成稳定趋势判断。"

    first_half = events[: max(1, len(events) // 2)]
    second_half = events[max(1, len(events) // 2) :]
    first_mean = mean(event.rms_amplitude for event in first_half)
    second_mean = mean(event.rms_amplitude for event in second_half)
    if second_mean > first_mean:
        direction = "后段平均幅度略高于前段"
    elif second_mean < first_mean:
        direction = "后段平均幅度略低于前段"
    else:
        direction = "前后段平均幅度整体接近"
    return "是", f"{direction}，该结果仅反映当前监测窗口内的相对变化。"


def _collect_document_strings(extractions: list[MedicalRecordExtraction], key: str) -> list[str]:
    values: list[str] = []
    for extraction in extractions:
        payload = extraction.structured_payload if isinstance(extraction.structured_payload, dict) else {}
        raw_value = payload.get(key)
        if isinstance(raw_value, list):
            values.extend(str(item) for item in raw_value if str(item).strip())
        elif isinstance(raw_value, str) and raw_value.strip():
            values.append(raw_value.strip())
    return values


@dataclass(slots=True)
class ReportAgentGeneration:
    markdown: str
    model_name: str
    rendered_user_prompt: str


class ReportContextAssembler:
    def assemble(
        self,
        session: Session,
        user: User,
        report: LongitudinalReport,
        trigger_message: str | None = None,
    ) -> dict[str, object]:
        profile = session.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
        monitoring_start = datetime.combine(report.monitoring_window_start, time.min, tzinfo=UTC)
        monitoring_end = datetime.combine(report.monitoring_window_end + timedelta(days=1), time.min, tzinfo=UTC)
        medication_start = datetime.combine(report.medication_window_start, time.min, tzinfo=UTC)
        medication_end = datetime.combine(report.medication_window_end + timedelta(days=1), time.min, tzinfo=UTC)
        monitoring_events = list(
            session.scalars(
                select(TremorEvent)
                .where(
                    TremorEvent.user_id == user.id,
                    TremorEvent.start_at >= monitoring_start,
                    TremorEvent.start_at < monitoring_end,
                )
                .order_by(TremorEvent.start_at)
            )
        )
        medication_logs = list(
            session.scalars(
                select(MedicationLog)
                .where(
                    MedicationLog.user_id == user.id,
                    MedicationLog.taken_at >= medication_start,
                    MedicationLog.taken_at < medication_end,
                )
                .order_by(MedicationLog.taken_at)
            )
        )
        extractions = list(
            session.scalars(
                select(MedicalRecordExtraction)
                .where(
                    MedicalRecordExtraction.archive_id == report.archive_id,
                    MedicalRecordExtraction.user_id == user.id,
                    MedicalRecordExtraction.status == "succeeded",
                )
                .order_by(MedicalRecordExtraction.created_at)
            )
        )
        archive = session.scalar(select(MedicalRecordArchive).where(MedicalRecordArchive.id == report.archive_id))
        device_binding, snapshot = get_latest_device_status(session, user.id)
        device_status = format_device_status(device_binding, snapshot)

        event_count = len(monitoring_events)
        avg_amplitude = round(mean(event.rms_amplitude for event in monitoring_events), 3) if monitoring_events else 0
        peak_amplitude = round(max((event.rms_amplitude for event in monitoring_events), default=0), 3)
        avg_duration = round(mean(event.duration_sec for event in monitoring_events), 1) if monitoring_events else 0
        max_duration = max((event.duration_sec for event in monitoring_events), default=0)
        avg_frequency = round(mean(event.dominant_hz for event in monitoring_events), 2) if monitoring_events else 0
        has_time_distribution, time_distribution_summary = _event_time_distribution_summary(monitoring_events)
        has_trend, trend_summary = _trend_summary(monitoring_events)
        patient_profile = {
            "name": profile.name if profile else user.display_name,
            "age": profile.age if profile else None,
            "gender": profile.gender if profile else None,
            "diagnosis": profile.diagnosis if profile else None,
            "duration": profile.duration if profile else None,
            "hospital": profile.hospital if profile else None,
        }
        monitoring_summary = {
            "event_count": event_count,
            "avg_duration_sec": avg_duration,
            "max_duration_sec": max_duration,
            "avg_amplitude": avg_amplitude,
            "max_amplitude": peak_amplitude,
            "avg_frequency_hz": avg_frequency,
            "events": [
                {
                    "start_at": event.start_at.isoformat(),
                    "duration_sec": event.duration_sec,
                    "dominant_hz": event.dominant_hz,
                    "rms_amplitude": event.rms_amplitude,
                    "confidence": event.confidence,
                }
                for event in monitoring_events[-50:]
            ],
        }
        medication_summary = {
            "count": len(medication_logs),
            "entries": [
                {
                    "name": item.name,
                    "dose": item.dose,
                    "taken_at": item.taken_at.isoformat(),
                    "status": item.status,
                }
                for item in medication_logs
            ],
        }
        extraction_snapshots = []
        information_gaps: list[str] = []
        for extraction in extractions:
            payload = extraction.structured_payload if isinstance(extraction.structured_payload, dict) else {}
            extraction_snapshots.append(
                {
                    "file_id": extraction.file_id,
                    "extraction_id": extraction.id,
                    "extraction_version": extraction.version,
                    "document_type": extraction.document_type,
                    "summary_text": extraction.summary_text,
                    "structured_payload": payload,
                }
            )
            gaps = payload.get("information_gaps")
            if isinstance(gaps, list):
                information_gaps.extend(str(item) for item in gaps if item)

        medications_text = _stringify_lines(
            [
                f"{item.taken_at.isoformat()} {item.name} {item.dose}（{item.status}）"
                for item in medication_logs[:10]
            ]
        )
        diagnoses = _collect_document_strings(extractions, "diagnoses_mentioned")
        symptoms = _collect_document_strings(extractions, "symptoms_mentioned")
        exams = _collect_document_strings(extractions, "exams_mentioned")
        family_history = _collect_document_strings(extractions, "family_history")
        lifestyle = _collect_document_strings(extractions, "lifestyle")
        non_motor_symptoms = _collect_document_strings(extractions, "non_motor_symptoms")
        adl_info = _collect_document_strings(extractions, "adl_info")
        physical_exam = _collect_document_strings(extractions, "physical_exam")
        scales = _collect_document_strings(extractions, "scales")

        report_purpose = "用于复诊前准备和健康管理归档。"
        if trigger_message and "复诊" in trigger_message:
            report_purpose = "用于复诊前重点问题梳理、病情沟通准备和健康管理归档。"

        return {
            "archive_id": archive.id if archive else report.archive_id,
            "archive_title": archive.title if archive else "当前未提供",
            "report_window": {
                "start": report.report_window_start.isoformat(),
                "end": report.report_window_end.isoformat(),
            },
            "monitoring_window_range": {
                "start": report.monitoring_window_start.isoformat(),
                "end": report.monitoring_window_end.isoformat(),
            },
            "medication_window": {
                "start": report.medication_window_start.isoformat(),
                "end": report.medication_window_end.isoformat(),
            },
            "selected_document_versions": [
                {"file_id": extraction.file_id, "document_version": 1} for extraction in extractions
            ],
            "selected_extraction_versions": [
                {"extraction_id": extraction.id, "file_id": extraction.file_id, "version": extraction.version}
                for extraction in extractions
            ],
            "patient_profile": patient_profile,
            "device_snapshot": (
                {
                    "connection": device_status.connection,
                    "connection_label": device_status.connection_label,
                    "battery": device_status.battery,
                    "firmware": device_status.firmware,
                }
                if device_status
                else None
            ),
            "monitoring_summary": monitoring_summary,
            "medication_summary": medication_summary,
            "document_summaries": extraction_snapshots,
            "information_gaps": information_gaps,
            "name": patient_profile["name"],
            "age": str(patient_profile["age"]) if patient_profile["age"] is not None else "当前未提供",
            "gender": patient_profile["gender"] or "当前未提供",
            "diagnosis_background": patient_profile["diagnosis"] or "当前未提供",
            "report_purpose": report_purpose,
            "monitoring_window": f"{report.monitoring_window_start.isoformat()} 至 {report.monitoring_window_end.isoformat()}",
            "tremor_event_count": str(event_count),
            "tremor_avg_amplitude": str(avg_amplitude),
            "tremor_peak_amplitude": str(peak_amplitude),
            "has_time_distribution": has_time_distribution,
            "time_distribution_summary": time_distribution_summary,
            "has_trend": has_trend,
            "trend_summary": trend_summary,
            "medication_records": medications_text,
            "past_history": _stringify_lines(diagnoses + symptoms),
            "family_history": _stringify_lines(family_history),
            "lifestyle": _stringify_lines(lifestyle),
            "non_motor_symptoms": _stringify_lines(non_motor_symptoms),
            "adl_info": _stringify_lines(adl_info),
            "physical_exam": _stringify_lines(physical_exam),
            "tests_and_imaging": _stringify_lines(exams),
            "scales": _stringify_lines(scales),
            "trigger_reason": trigger_message or "用户主动发起健康报告生成请求。",
            "supplemental_focus": trigger_message or "当前未提供额外补充关注点。",
        }


class HealthReportAgent:
    agent_type = "health_report_agent"

    def build_user_prompt(self, context: dict[str, object]) -> str:
        normalized_context = {
            key: (
                value
                if isinstance(value, str) and value.strip()
                else json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else "当前未提供。"
            )
            for key, value in context.items()
        }
        return REPORT_AGENT_USER_TEMPLATE.substitute(normalized_context)

    def generate(
        self,
        *,
        context: dict[str, object],
    ) -> ReportAgentGeneration:
        settings = get_settings()
        rendered_user_prompt = self.build_user_prompt(context)
        payload = {
            "model": settings.dashscope_report_agent_model,
            "messages": [
                {"role": "system", "content": REPORT_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": rendered_user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4200,
        }
        data = post_chat_completion(payload)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("报告生成 Agent 返回格式异常。")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("报告生成 Agent 返回空内容。")
        markdown = content.strip()
        markdown = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", markdown)
        markdown = re.sub(r"\n?```$", "", markdown).strip()
        return ReportAgentGeneration(
            markdown=markdown,
            model_name=str(data.get("model") or settings.dashscope_report_agent_model),
            rendered_user_prompt=rendered_user_prompt,
        )
