from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClinicalSessionDep, CurrentUserDep, IdentitySessionDep
from app.core.config import get_settings
from app.core.security import hash_device_key, hash_password, verify_password
from app.models.clinical import ConsentSettings, DeviceBinding, PatientProfile
from app.models.identity import User
from app.schemas.auth import CurrentUserResponse
from app.schemas.domain import (
    BindingConflictError,
    ConsentSettingsDTO,
    DeviceBindingRequest,
    DeviceBindingResponse,
    MeProfileResponse,
    PatientProfileUpsertRequest,
    PatientProfileUpsertResponse,
)
from app.services.dashboard import format_device_status, get_latest_device_status
from app.services.user_management import (
    build_completion_status,
    build_device_binding_dto,
    build_patient_profile_dto,
    ensure_consent_settings,
    get_active_device_binding,
    sync_user_state,
    unbind_device,
)

router = APIRouter()
settings = get_settings()


def get_identity_user(identity_session: IdentitySessionDep, user_id: str) -> User:
    user = identity_session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.get("", response_model=CurrentUserResponse)
def get_me(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> CurrentUserResponse:
    return CurrentUserResponse(user=sync_user_state(current_user, clinical_session))


@router.get("/profile", response_model=MeProfileResponse)
def get_profile(current_user: CurrentUserDep, clinical_session: ClinicalSessionDep) -> MeProfileResponse:
    profile = clinical_session.scalar(select(PatientProfile).where(PatientProfile.user_id == current_user.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not completed")
    consent = clinical_session.scalar(select(ConsentSettings).where(ConsentSettings.user_id == current_user.id))
    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)

    return MeProfileResponse(
        patient_profile=build_patient_profile_dto(profile, device_binding),
        device_status=format_device_status(device_binding, snapshot),
        consent_settings=ConsentSettingsDTO(
            share_with_doctor=consent.share_with_doctor,
            rag_analysis_enabled=consent.rag_analysis_enabled,
            cloud_sync_enabled=consent.cloud_sync_enabled,
        ),
    )


@router.put("/profile", response_model=PatientProfileUpsertResponse)
def upsert_profile(
    payload: PatientProfileUpsertRequest,
    current_user: CurrentUserDep,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> PatientProfileUpsertResponse:
    profile = clinical_session.scalar(select(PatientProfile).where(PatientProfile.user_id == current_user.id))
    if profile:
        profile.name = payload.name
        profile.age = payload.age
        profile.gender = payload.gender
        profile.diagnosis = payload.diagnosis
        profile.duration = payload.duration
        profile.hospital = payload.hospital
    else:
        profile = PatientProfile(user_id=current_user.id, **payload.model_dump())
        clinical_session.add(profile)
        clinical_session.flush()

    ensure_consent_settings(clinical_session, current_user.id)
    user = get_identity_user(identity_session, current_user.id)
    current_user_summary = sync_user_state(user, clinical_session)
    clinical_session.commit()
    identity_session.commit()

    return PatientProfileUpsertResponse(
        patient_profile=build_patient_profile_dto(
            profile,
            get_active_device_binding(clinical_session, current_user.id),
        ),
        completion=build_completion_status(clinical_session, current_user_summary.id),
    )


@router.get("/device-binding", response_model=DeviceBindingResponse)
def get_device_binding(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> DeviceBindingResponse:
    binding = get_active_device_binding(clinical_session, current_user.id)
    return DeviceBindingResponse(
        device_binding=build_device_binding_dto(binding),
        completion=build_completion_status(clinical_session, current_user.id),
    )


@router.post(
    "/device-binding",
    response_model=DeviceBindingResponse,
    responses={409: {"model": BindingConflictError}},
)
def bind_device(
    payload: DeviceBindingRequest,
    current_user: CurrentUserDep,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> DeviceBindingResponse:
    profile = clinical_session.scalar(select(PatientProfile).where(PatientProfile.user_id == current_user.id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile must be completed before binding a device",
        )

    target_binding = clinical_session.scalar(
        select(DeviceBinding).where(DeviceBinding.device_serial == payload.device_serial)
    )
    if not target_binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if not target_binding.activation_code_hash or not verify_password(
        payload.activation_code,
        target_binding.activation_code_hash,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activation code")

    if (
        target_binding.binding_status == "bound"
        and target_binding.user_id
        and target_binding.user_id != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already bound")

    current_binding = get_active_device_binding(clinical_session, current_user.id)
    if current_binding and current_binding.id != target_binding.id:
        unbind_device(current_binding)

    target_binding.user_id = current_user.id
    target_binding.binding_status = "bound"
    target_binding.bound_at = datetime.now(UTC)
    target_binding.unbound_at = None
    target_binding.is_active = True

    user = get_identity_user(identity_session, current_user.id)
    sync_user_state(user, clinical_session)
    clinical_session.commit()
    identity_session.commit()

    return DeviceBindingResponse(
        device_binding=build_device_binding_dto(target_binding),
        completion=build_completion_status(clinical_session, current_user.id),
    )


@router.post("/device-binding/demo", response_model=DeviceBindingResponse)
def bind_demo_device(
    current_user: CurrentUserDep,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> DeviceBindingResponse:
    profile = clinical_session.scalar(select(PatientProfile).where(PatientProfile.user_id == current_user.id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile must be completed before binding a device",
        )

    current_binding = get_active_device_binding(clinical_session, current_user.id)
    if current_binding:
        return DeviceBindingResponse(
            device_binding=build_device_binding_dto(current_binding),
            completion=build_completion_status(clinical_session, current_user.id),
        )

    demo_binding = clinical_session.scalar(
        select(DeviceBinding).where(
            DeviceBinding.device_serial == settings.demo_available_device_serial,
            DeviceBinding.is_active.is_(True),
        )
    )

    if demo_binding and demo_binding.binding_status == "available":
        target_binding = demo_binding
        target_binding.user_id = current_user.id
        target_binding.binding_status = "bound"
        target_binding.bound_at = datetime.now(UTC)
        target_binding.unbound_at = None
    else:
        target_binding = DeviceBinding(
            user_id=current_user.id,
            device_serial=f"TG-DEMO-{uuid4().hex[:8].upper()}",
            device_name="TremorGuard Demo",
            firmware_version="v1.0.6",
            api_key_hash=hash_device_key(f"demo-device-{uuid4()}"),
            activation_code_hash=hash_password("demo-skip"),
            binding_status="bound",
            bound_at=datetime.now(UTC),
            unbound_at=None,
            is_active=True,
        )
        clinical_session.add(target_binding)

    user = get_identity_user(identity_session, current_user.id)
    sync_user_state(user, clinical_session)
    clinical_session.commit()
    identity_session.commit()

    return DeviceBindingResponse(
        device_binding=build_device_binding_dto(target_binding),
        completion=build_completion_status(clinical_session, current_user.id),
    )


@router.delete("/device-binding", response_model=DeviceBindingResponse)
def delete_device_binding(
    current_user: CurrentUserDep,
    identity_session: IdentitySessionDep,
    clinical_session: ClinicalSessionDep,
) -> DeviceBindingResponse:
    binding = get_active_device_binding(clinical_session, current_user.id)
    if binding:
        unbind_device(binding)

    user = get_identity_user(identity_session, current_user.id)
    sync_user_state(user, clinical_session)
    clinical_session.commit()
    identity_session.commit()

    return DeviceBindingResponse(
        device_binding=None,
        completion=build_completion_status(clinical_session, current_user.id),
    )
