from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical import ConsentSettings, DeviceBinding, PatientProfile
from app.models.identity import User
from app.schemas.auth import CurrentUserDTO
from app.schemas.domain import (
    DeviceBindingDTO,
    PatientProfileDTO,
    ProfileCompletionStatus,
)


def resolve_onboarding_state(has_profile: bool, has_bound_device: bool) -> str:
    if not has_profile:
        return "profile_required"
    if not has_bound_device:
        return "device_binding_required"
    return "active"


def resolve_user_status(onboarding_state: str) -> str:
    if onboarding_state == "active":
        return "active"
    return "pending_onboarding"


def get_active_device_binding(session: Session, user_id: str) -> DeviceBinding | None:
    return session.scalar(
        select(DeviceBinding).where(
            DeviceBinding.user_id == user_id,
            DeviceBinding.binding_status == "bound",
            DeviceBinding.is_active.is_(True),
        )
    )


def build_completion_status(session: Session, user_id: str) -> ProfileCompletionStatus:
    has_profile = session.scalar(
        select(PatientProfile.id).where(PatientProfile.user_id == user_id)
    ) is not None
    has_bound_device = get_active_device_binding(session, user_id) is not None
    return ProfileCompletionStatus(
        onboarding_state=resolve_onboarding_state(has_profile, has_bound_device),
        has_profile=has_profile,
        has_bound_device=has_bound_device,
    )


def sync_user_state(user: User, clinical_session: Session) -> CurrentUserDTO:
    completion = build_completion_status(clinical_session, user.id)
    user.onboarding_state = completion.onboarding_state
    user.status = resolve_user_status(completion.onboarding_state)

    active_device = get_active_device_binding(clinical_session, user.id)
    return CurrentUserDTO(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        onboarding_state=user.onboarding_state,
        last_login_at=user.last_login_at,
        has_profile=completion.has_profile,
        has_bound_device=completion.has_bound_device,
        bound_device_serial=active_device.device_serial if active_device else None,
    )


def ensure_consent_settings(session: Session, user_id: str) -> ConsentSettings:
    consent = session.scalar(select(ConsentSettings).where(ConsentSettings.user_id == user_id))
    if consent:
        return consent

    consent = ConsentSettings(
        user_id=user_id,
        share_with_doctor=True,
        rag_analysis_enabled=True,
        cloud_sync_enabled=True,
    )
    session.add(consent)
    session.flush()
    return consent


def build_patient_profile_dto(profile: PatientProfile, device_binding: DeviceBinding | None) -> PatientProfileDTO:
    return PatientProfileDTO(
        id=profile.user_id,
        name=profile.name,
        age=profile.age,
        gender=profile.gender,
        diagnosis=profile.diagnosis,
        duration=profile.duration,
        hospital=profile.hospital,
        device_id=device_binding.device_serial if device_binding else "未绑定",
    )


def build_device_binding_dto(binding: DeviceBinding | None) -> DeviceBindingDTO | None:
    if not binding:
        return None

    return DeviceBindingDTO(
        id=binding.id,
        device_serial=binding.device_serial,
        device_name=binding.device_name,
        firmware_version=binding.firmware_version,
        binding_status=binding.binding_status,
        bound_at=binding.bound_at,
        unbound_at=binding.unbound_at,
    )


def unbind_device(binding: DeviceBinding) -> None:
    binding.user_id = None
    binding.binding_status = "available"
    binding.unbound_at = datetime.now(UTC)
