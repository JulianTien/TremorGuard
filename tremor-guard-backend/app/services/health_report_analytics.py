from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from statistics import mean
from zoneinfo import ZoneInfo

MISSING_DATA_PLACEHOLDER = "数据不足/待补充。"
DISCLAIMER_TEXT = "本报告仅供健康管理与复诊沟通参考，不能替代医生诊断、分期、处方或药量调整。"


def mask_patient_name(name: str | None) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        return "当前用户"
    if len(normalized) == 1:
        return f"{normalized}**"
    return f"{normalized[0]}**"


def report_patient_token(user_id: str | None) -> str:
    digest = sha256(str(user_id or "unknown").encode("utf-8")).hexdigest()[:8].upper()
    return f"TG{digest}"


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _local_dt(value: object, timezone_name: str) -> datetime | None:
    parsed = _parse_dt(value)
    if parsed is None:
        return None
    return parsed.astimezone(ZoneInfo(timezone_name))


def _event_period(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def _severity_label(amplitude: float) -> str:
    if amplitude < 0.3:
        return "light"
    if amplitude <= 0.6:
        return "moderate"
    return "severe"


def _zh_period(key: str) -> str:
    return {
        "morning": "晨间",
        "afternoon": "午后",
        "evening": "晚间",
        "night": "夜间",
    }.get(key, key)


def _zh_severity(key: str) -> str:
    return {"light": "轻度", "moderate": "中度", "severe": "重度"}.get(key, key)


def _round(value: float | int | None, digits: int = 3) -> float:
    return round(float(value or 0), digits)


def build_health_report_analytics(
    context: dict[str, object],
    *,
    user_id: str,
    report_id: str,
    generated_at: datetime,
    timezone_name: str,
    mask_identifiers: bool,
) -> dict[str, object]:
    patient = context.get("patient_profile") if isinstance(context.get("patient_profile"), dict) else {}
    monitoring = context.get("monitoring_summary") if isinstance(context.get("monitoring_summary"), dict) else {}
    medication = context.get("medication_summary") if isinstance(context.get("medication_summary"), dict) else {}

    events = [event for event in monitoring.get("events", []) if isinstance(event, dict)]
    medications = [entry for entry in medication.get("entries", []) if isinstance(entry, dict)]
    local_events = [
        {
            **event,
            "local_start_at": local_dt,
            "amplitude": _round(event.get("rms_amplitude"), 3),
        }
        for event in events
        if (local_dt := _local_dt(event.get("start_at"), timezone_name)) is not None
    ]
    local_medications = [
        {**entry, "local_taken_at": local_dt}
        for entry in medications
        if (local_dt := _local_dt(entry.get("taken_at"), timezone_name)) is not None
    ]

    event_count = int(monitoring.get("event_count") or len(local_events))
    avg_amplitude = _round(monitoring.get("avg_amplitude"), 3)
    max_amplitude = _round(monitoring.get("max_amplitude"), 3)

    period_counter: Counter[str] = Counter(_event_period(item["local_start_at"].hour) for item in local_events)
    severity_counter: Counter[str] = Counter(_severity_label(float(item["amplitude"])) for item in local_events)
    hourly_counter: Counter[int] = Counter(item["local_start_at"].hour for item in local_events)
    amplitude_values = [float(item["amplitude"]) for item in local_events]

    taken_count = sum(1 for entry in medications if str(entry.get("status")) == "taken")
    pending_count = sum(1 for entry in medications if str(entry.get("status")) == "pending")
    medication_count = int(medication.get("count") or len(medications))
    adherence_rate = round(taken_count / medication_count, 3) if medication_count else None

    medication_windows = _build_medication_windows(local_events, local_medications)
    baseline = _build_baseline_summary(local_events)
    highlights = _build_highlights(
        event_count=event_count,
        avg_amplitude=avg_amplitude,
        max_amplitude=max_amplitude,
        period_counter=period_counter,
        severity_counter=severity_counter,
        medication_count=medication_count,
        adherence_rate=adherence_rate,
        baseline=baseline,
    )

    raw_name = str(patient.get("name") or "当前用户")
    display_name = mask_patient_name(raw_name) if mask_identifiers else raw_name
    generated_local = generated_at.astimezone(ZoneInfo(timezone_name))
    patient_token = report_patient_token(user_id)

    severity_distribution = [
        _distribution_row(key, count, event_count, _zh_severity(key))
        for key, count in (
            ("light", severity_counter.get("light", 0)),
            ("moderate", severity_counter.get("moderate", 0)),
            ("severe", severity_counter.get("severe", 0)),
        )
    ]
    period_distribution = [
        _distribution_row(key, period_counter.get(key, 0), event_count, _zh_period(key))
        for key in ("morning", "afternoon", "evening", "night")
    ]

    analytics = {
        "patient_token": patient_token,
        "display_patient_profile": {
            **patient,
            "name": display_name,
            "patient_token": patient_token,
        },
        "report_metadata": {
            "report_id": report_id,
            "generated_at": generated_local.isoformat(),
            "timezone": timezone_name,
            "mask_identifiers": mask_identifiers,
            "report_type_label": "TremorGuard 监测周期分析报告",
        },
        "kpi_cards": [
            {"label": "累计震颤事件", "value": str(event_count), "unit": "次", "hint": "报告监测窗口内记录"},
            {"label": "平均幅度", "value": f"{avg_amplitude:.3f}", "unit": "", "hint": "RMS 幅度均值"},
            {"label": "峰值幅度", "value": f"{max_amplitude:.3f}", "unit": "", "hint": "窗口内最高记录"},
            {
                "label": "用药依从率",
                "value": f"{int(round(adherence_rate * 100))}%" if adherence_rate is not None else "待补充",
                "unit": "",
                "hint": f"已执行 {taken_count}/{medication_count}" if medication_count else "暂无用药记录",
            },
        ],
        "tremor_severity_distribution": severity_distribution,
        "time_distribution": period_distribution,
        "hourly_event_counts": [{"hour": hour, "count": hourly_counter.get(hour, 0)} for hour in range(24)],
        "amplitude_histogram": _amplitude_histogram(amplitude_values),
        "medication_adherence": {
            "total": medication_count,
            "taken": taken_count,
            "pending": pending_count,
            "rate": adherence_rate,
            "summary": (
                f"用药窗口内记录 {medication_count} 条，其中已执行 {taken_count} 条，待执行 {pending_count} 条。"
                if medication_count
                else "用药窗口内暂无结构化用药记录。"
            ),
        },
        "medication_correlation_summary": medication_windows,
        "baseline_summary": baseline,
        "monitoring_highlights": highlights,
        "visualization_data": {
            "hourly_event_counts": [{"hour": hour, "count": hourly_counter.get(hour, 0)} for hour in range(24)],
            "amplitude_histogram": _amplitude_histogram(amplitude_values),
            "medication_timeline": _medication_timeline(local_medications),
            "medication_scatter": _medication_scatter(local_events, local_medications),
            "severity_distribution": severity_distribution,
        },
        "analytics_summary_text": _analytics_summary_text(
            event_count=event_count,
            avg_amplitude=avg_amplitude,
            max_amplitude=max_amplitude,
            severity_distribution=severity_distribution,
            period_distribution=period_distribution,
            medication_count=medication_count,
            taken_count=taken_count,
            medication_windows=medication_windows,
            baseline=baseline,
        ),
        "clinical_reference_notes": _clinical_reference_notes(),
        "data_completion_guidance": _data_completion_guidance(),
        "knowledge_cards": _knowledge_cards(),
        "followup_checklist": _followup_checklist(),
        "self_assessment_questions": _self_assessment_questions(),
    }
    return analytics


def enrich_health_report_context(
    context: dict[str, object],
    *,
    user_id: str,
    report_id: str,
    generated_at: datetime,
    timezone_name: str,
    mask_identifiers: bool,
) -> dict[str, object]:
    analytics = build_health_report_analytics(
        context,
        user_id=user_id,
        report_id=report_id,
        generated_at=generated_at,
        timezone_name=timezone_name,
        mask_identifiers=mask_identifiers,
    )
    context.update(analytics)
    display_profile = analytics["display_patient_profile"]
    if isinstance(display_profile, dict):
        context["name"] = display_profile.get("name") or context.get("name")
    context["baseline_summary"] = analytics["baseline_summary"]
    context["medication_correlation_summary"] = analytics["medication_correlation_summary"]
    context["tremor_severity_distribution"] = analytics["tremor_severity_distribution"]
    return context


def _distribution_row(key: str, count: int, total: int, label: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "count": count,
        "ratio": round(count / total, 3) if total else 0,
    }


def _amplitude_histogram(values: list[float]) -> list[dict[str, object]]:
    buckets = [
        ("0.0-0.3", 0, 0.3),
        ("0.3-0.6", 0.3, 0.6),
        (">0.6", 0.6, float("inf")),
    ]
    rows = []
    for label, lower, upper in buckets:
        count = sum(1 for value in values if lower <= value < upper)
        rows.append({"label": label, "count": count})
    return rows


def _build_medication_windows(
    events: list[dict[str, object]],
    medications: list[dict[str, object]],
) -> dict[str, object]:
    if not events or not medications:
        return {
            "windows": [],
            "summary": "当前缺少可匹配的震颤事件或用药时间戳，暂不能形成服药前后关联观察。",
            "wearing_off_signal": "未形成足够数据线索。",
        }

    rows = []
    for medication in medications:
        taken_at = medication["local_taken_at"]
        before = [
            float(event["amplitude"])
            for event in events
            if -180 <= (event["local_start_at"] - taken_at).total_seconds() / 60 < 0
        ]
        after_1h = [
            float(event["amplitude"])
            for event in events
            if 0 <= (event["local_start_at"] - taken_at).total_seconds() / 60 <= 60
        ]
        after_3h = [
            float(event["amplitude"])
            for event in events
            if 60 < (event["local_start_at"] - taken_at).total_seconds() / 60 <= 180
        ]
        rows.append(
            {
                "taken_at": taken_at.strftime("%H:%M"),
                "name": medication.get("name") or "用药记录",
                "dose": medication.get("dose") or "",
                "status": medication.get("status") or "",
                "before_avg": _average_or_none(before),
                "after_1h_avg": _average_or_none(after_1h),
                "after_3h_avg": _average_or_none(after_3h),
                "before_count": len(before),
                "after_1h_count": len(after_1h),
                "after_3h_count": len(after_3h),
            }
        )

    after_3h_values = [row["after_3h_avg"] for row in rows if row["after_3h_avg"] is not None]
    after_1h_values = [row["after_1h_avg"] for row in rows if row["after_1h_avg"] is not None]
    if after_1h_values and after_3h_values and mean(after_3h_values) > mean(after_1h_values):
        wearing_off_signal = "服药后 3 小时窗口的平均幅度高于服药后 1 小时窗口，提示存在需要复诊沟通的剂末波动数据线索。"
    else:
        wearing_off_signal = "当前数据未形成稳定的剂末波动或开关波动线索，仍建议持续记录服药与症状时间关系。"
    return {
        "windows": rows,
        "summary": "已按服药时间对震颤事件进行前后窗口归类；该观察仅用于复诊沟通，不能单独判断疗效。",
        "wearing_off_signal": wearing_off_signal,
    }


def _average_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 3)


def _build_baseline_summary(events: list[dict[str, object]]) -> dict[str, object]:
    by_date: dict[str, list[float]] = {}
    for event in events:
        local_dt = event["local_start_at"]
        by_date.setdefault(local_dt.date().isoformat(), []).append(float(event["amplitude"]))
    if len(by_date) < 2:
        return {
            "available": False,
            "summary": "当前报告窗口内不足两个自然日，暂不能形成稳定历史基线对比。",
        }
    ordered = sorted(by_date.items())
    previous_values = [value for _, values in ordered[:-1] for value in values]
    latest_date, latest_values = ordered[-1]
    previous_avg = _average_or_none(previous_values)
    latest_avg = _average_or_none(latest_values)
    delta = round((latest_avg or 0) - (previous_avg or 0), 3)
    if delta > 0.05:
        trend = "最近自然日平均幅度高于前期均值"
    elif delta < -0.05:
        trend = "最近自然日平均幅度低于前期均值"
    else:
        trend = "最近自然日与前期平均幅度整体接近"
    return {
        "available": True,
        "latest_date": latest_date,
        "previous_avg_amplitude": previous_avg,
        "latest_avg_amplitude": latest_avg,
        "delta": delta,
        "summary": f"{trend}，差值约 {delta:+.3f}，该结果仅反映当前 TremorGuard 监测窗口内的相对变化。",
    }


def _build_highlights(
    *,
    event_count: int,
    avg_amplitude: float,
    max_amplitude: float,
    period_counter: Counter[str],
    severity_counter: Counter[str],
    medication_count: int,
    adherence_rate: float | None,
    baseline: dict[str, object],
) -> list[str]:
    highlights = [
        f"监测窗口内记录 {event_count} 次震颤事件，平均幅度 {avg_amplitude:.3f}，峰值幅度 {max_amplitude:.3f}。",
    ]
    if event_count:
        busiest_period, busiest_count = max(period_counter.items(), key=lambda item: item[1])
        highlights.append(f"{_zh_period(busiest_period)}记录相对集中，共 {busiest_count} 次，适合作为复诊沟通重点。")
        severe_count = severity_counter.get("severe", 0)
        if severe_count:
            highlights.append(f"重度幅度事件记录 {severe_count} 次，建议结合诱因、持续时间和服药时间继续追踪。")
    if medication_count:
        rate_text = f"{int(round((adherence_rate or 0) * 100))}%"
        highlights.append(f"用药窗口内有 {medication_count} 条记录，当前记录依从率约 {rate_text}。")
    if baseline.get("available"):
        highlights.append(str(baseline.get("summary")))
    return highlights


def _medication_timeline(medications: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "time": item["local_taken_at"].strftime("%H:%M"),
            "name": item.get("name") or "用药记录",
            "dose": item.get("dose") or "",
            "status": item.get("status") or "",
        }
        for item in medications
    ]


def _medication_scatter(
    events: list[dict[str, object]],
    medications: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not medications:
        return []
    first_medication = medications[0]["local_taken_at"]
    return [
        {
            "minutes_from_first_dose": round((event["local_start_at"] - first_medication).total_seconds() / 60),
            "amplitude": event["amplitude"],
        }
        for event in events
    ]


def _analytics_summary_text(
    *,
    event_count: int,
    avg_amplitude: float,
    max_amplitude: float,
    severity_distribution: list[dict[str, object]],
    period_distribution: list[dict[str, object]],
    medication_count: int,
    taken_count: int,
    medication_windows: dict[str, object],
    baseline: dict[str, object],
) -> str:
    severity_text = "；".join(
        f"{row['label']} {row['count']} 次（{int(round(float(row['ratio']) * 100))}%）"
        for row in severity_distribution
    )
    period_text = "；".join(f"{row['label']} {row['count']} 次" for row in period_distribution)
    return "\n".join(
        [
            f"- 核心监测：累计 {event_count} 次震颤事件，平均幅度 {avg_amplitude:.3f}，峰值 {max_amplitude:.3f}。",
            f"- 幅度分层：{severity_text}。",
            f"- 时间分布：{period_text}。",
            f"- 用药记录：共 {medication_count} 条，已执行 {taken_count} 条；依从率用于记录完整性观察，不代表疗效判断。",
            f"- 用药-症状关联：{medication_windows['wearing_off_signal']}",
            f"- 历史基线：{baseline['summary']}",
        ]
    )


def _clinical_reference_notes() -> list[str]:
    return [
        "多巴丝肼用于补充左旋多巴并减少外周代谢，常见观察重点包括恶心、头晕、体位性低血压、异动样动作和精神行为变化。",
        "运动训练可作为帕金森病长期管理的重要组成部分；太极、步态与平衡训练、LSVT BIG 等训练需结合个人能力和医生或治疗师建议。",
        "MDS-UPDRS、Hoehn-Yahr、MoCA/MMSE 等量表需要由专业人员结合面诊或标准化问卷完成，本报告不替代量表评估。",
    ]


def _data_completion_guidance() -> list[str]:
    return [
        "建议补充 MDS-UPDRS III、Hoehn-Yahr、MoCA 或 MMSE、非运动症状问卷、跌倒风险与日常生活能力记录。",
        "建议复诊前记录震颤起止时间、诱因、服药时间、餐食时间、睡眠、情绪压力和伴随症状。",
        "建议携带既往门诊病历、影像或化验报告原文、当前药盒或药品清单，以及近期 TremorGuard 监测报告。",
    ]


def _knowledge_cards() -> list[dict[str, str]]:
    return [
        {
            "title": "剂末现象",
            "body": "指临近下一次服药前症状重新加重的现象。本报告只能提示时间相关线索，是否存在该现象需由医生结合病史判断。",
        },
        {
            "title": "震颤幅度分层",
            "body": "本系统按设备 RMS 幅度进行轻度、中度、重度分层，用于趋势观察，不等同于临床严重程度分级。",
        },
        {
            "title": "蛋白质再分配饮食",
            "body": "部分患者会关注蛋白摄入与左旋多巴吸收的关系；是否调整饮食结构应先咨询医生或营养师。",
        },
    ]


def _followup_checklist() -> list[str]:
    return [
        "带上本报告 PDF、既往病历原文、当前用药清单和最近一周症状日记。",
        "向医生说明震颤最明显的时段、服药后变化、是否跌倒、是否出现头晕或异动样动作。",
        "询问是否需要补充量表评估、影像/化验复查、康复训练或居家安全评估。",
    ]


def _self_assessment_questions() -> list[str]:
    return [
        "过去一周震颤最明显的时间段是什么？是否与服药、进餐、紧张或疲劳相关？",
        "是否出现跌倒、近跌倒、起身头晕、睡眠障碍、便秘、情绪低落或记忆注意力变化？",
        "是否漏服、延迟服药，或出现服药后不适？请记录具体时间和表现。",
    ]
