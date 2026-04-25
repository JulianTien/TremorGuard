from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.clinical import DeviceBinding, DeviceStatusSnapshot, MedicationLog, TremorEvent
from app.schemas.domain import (
    AiInsightDTO,
    DeviceStatusDTO,
    OverviewEvidenceReadinessDTO,
    TremorMetricSummaryDTO,
    TremorTrendPointDTO,
)

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def to_display_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(DISPLAY_TZ)


def get_latest_device_status(session: Session, user_id: str) -> tuple[DeviceBinding | None, DeviceStatusSnapshot | None]:
    device_binding = session.scalar(
        select(DeviceBinding)
        .where(
            DeviceBinding.user_id == user_id,
            DeviceBinding.binding_status == "bound",
            DeviceBinding.is_active.is_(True),
        )
        .order_by(desc(DeviceBinding.bound_at), desc(DeviceBinding.created_at))
    )
    snapshot = session.scalar(
        select(DeviceStatusSnapshot)
        .where(DeviceStatusSnapshot.user_id == user_id)
        .order_by(desc(DeviceStatusSnapshot.recorded_at))
    )
    return device_binding, snapshot


def format_device_status(
    device_binding: DeviceBinding | None, snapshot: DeviceStatusSnapshot | None
) -> DeviceStatusDTO:
    if snapshot:
        last_sync_label = to_display_datetime(snapshot.last_sync_at).strftime("%H:%M 最后同步")
        return DeviceStatusDTO(
            battery=snapshot.battery_level,
            connection=snapshot.connection,
            connection_label=snapshot.connection_label,
            last_sync=last_sync_label,
            available_days=snapshot.available_days_label,
            firmware=snapshot.firmware_version,
        )

    firmware = device_binding.firmware_version if device_binding else "unknown"
    return DeviceStatusDTO(
        battery=0,
        connection="offline",
        connection_label="未连接",
        last_sync="暂无同步记录",
        available_days="预计可用 0 天",
        firmware=firmware,
    )


def build_metric_summaries(
    events_today: list[TremorEvent], events_yesterday: list[TremorEvent]
) -> list[TremorMetricSummaryDTO]:
    count_today = len(events_today)
    count_yesterday = len(events_yesterday)
    avg_hz = round(mean([event.dominant_hz for event in events_today]), 1) if events_today else 0
    avg_duration = round(mean([event.duration_sec for event in events_today])) if events_today else 0
    longest_duration = max((event.duration_sec for event in events_today), default=0)

    delta_percent = 0
    if count_yesterday:
        delta_percent = round(((count_today - count_yesterday) / count_yesterday) * 100)
    subtitle = f"较昨日 {'+' if delta_percent >= 0 else ''}{delta_percent}%"
    tone = "alert" if count_today >= count_yesterday else "safe"

    return [
        TremorMetricSummaryDTO(
            label="今日发作频次",
            value=count_today,
            unit="次",
            subtitle=subtitle,
            tone=tone,
        ),
        TremorMetricSummaryDTO(
            label="平均主频率",
            value=avg_hz,
            unit="Hz",
            subtitle="典型PD频段: 4-6Hz",
            tone="neutral",
        ),
        TremorMetricSummaryDTO(
            label="平均持续时长",
            value=avg_duration,
            unit="秒",
            subtitle=f"最长: {longest_duration}秒",
            tone="neutral",
        ),
    ]


def build_trend_points(events: list[TremorEvent], medications: list[MedicationLog], target_date: date) -> list[TremorTrendPointDTO]:
    bucket_values: dict[int, list[float]] = defaultdict(list)
    medication_by_bucket: dict[int, MedicationLog] = {}

    for event in events:
        local_time = to_display_datetime(event.start_at)
        bucket = min(local_time.hour // 2, 11)
        bucket_values[bucket].append(round(event.rms_amplitude, 2))

    for medication in medications:
        local_time = to_display_datetime(medication.taken_at)
        bucket = min(local_time.hour // 2, 11)
        medication_by_bucket[bucket] = medication

    points: list[TremorTrendPointDTO] = []
    for bucket in range(12):
        hour = bucket * 2
        label = f"{hour:02d}:00"
        amplitudes = bucket_values.get(bucket, [])
        medication = medication_by_bucket.get(bucket)
        point_label = (
            to_display_datetime(medication.taken_at).strftime("%H:%M 服药")
            if medication
            else None
        )
        points.append(
            TremorTrendPointDTO(
                time=label,
                amplitude=round(mean(amplitudes), 2) if amplitudes else 0.0,
                label=point_label,
                medication_taken=bool(medication),
            )
        )

    points.append(
        TremorTrendPointDTO(
            time="24:00",
            amplitude=points[-1].amplitude if points else 0.0,
        )
    )
    return points


def build_overview_insight(
    trend_points: list[TremorTrendPointDTO], medications: list[MedicationLog]
) -> AiInsightDTO:
    peak_points = sorted(
        [point for point in trend_points if point.amplitude > 0],
        key=lambda point: point.amplitude,
        reverse=True,
    )[:2]
    medication_labels = (
        ", ".join(to_display_datetime(med.taken_at).strftime("%H:%M") for med in medications)
        or "暂无记录"
    )

    if peak_points:
        peak_label = " 及 ".join(point.time for point in peak_points)
        summary = (
            f"今日 {peak_label} 左右出现较明显的震颤波峰。结合您的服药时间（{medication_labels}），"
            "这些时段值得在复诊时向医生重点说明，用于观察药效波动规律。"
        )
    else:
        summary = (
            f"今日暂未观测到明显异常波峰。系统已持续关联您的服药时间（{medication_labels}），"
            "后续若出现集中波动，可用于辅助医生评估药效周期。"
        )

    return AiInsightDTO(id="overview-insight", title="AI 医生摘要洞察", summary=summary)


def build_evidence_readiness(
    *,
    has_device_binding: bool,
    events_today: list[TremorEvent],
    medications: list[MedicationLog],
    medical_record_archive_count: int,
) -> OverviewEvidenceReadinessDTO:
    has_monitoring_events = len(events_today) > 0
    has_medication_logs = len(medications) > 0
    has_medical_record_archives = medical_record_archive_count > 0

    ai_interpretation_ready = has_device_binding and (
        has_monitoring_events or has_medication_logs or has_medical_record_archives
    )
    rehab_plan_ready = has_monitoring_events and has_medication_logs
    health_report_ready = has_monitoring_events or has_medication_logs or has_medical_record_archives

    next_steps: list[str] = []
    if not has_monitoring_events:
        next_steps.append("继续佩戴设备采集监测数据")
    if not has_medication_logs:
        next_steps.append("补充今日用药记录")
    if not has_medical_record_archives:
        next_steps.append("补充病历档案以增强 AI 解读")
    if not next_steps:
        next_steps.append("前往 AI 医生解读当前状态")

    return OverviewEvidenceReadinessDTO(
        has_device_binding=has_device_binding,
        has_monitoring_events=has_monitoring_events,
        monitoring_event_count=len(events_today),
        has_medication_logs=has_medication_logs,
        medication_log_count=len(medications),
        has_medical_record_archives=has_medical_record_archives,
        medical_record_archive_count=medical_record_archive_count,
        ai_interpretation_ready=ai_interpretation_ready,
        rehab_plan_ready=rehab_plan_ready,
        health_report_ready=health_report_ready,
        next_steps=next_steps,
    )
