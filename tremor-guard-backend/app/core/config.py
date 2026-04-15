from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TremorGuard Backend"
    api_v1_prefix: str = "/v1"
    clinical_database_url: str = "sqlite:///./clinical.db"
    identity_database_url: str = "sqlite:///./identity.db"
    secret_key: str = "dev-secret-key-change-me-and-use-at-least-32-bytes"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    device_key_salt: str = "tremor-guard-device-salt"
    activation_code_salt: str = "tremor-guard-activation-code-salt"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:4174",
        "http://127.0.0.1:4174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    demo_user_email: str = "patient@tremorguard.local"
    demo_user_password: str = "tg-demo-password"
    demo_device_key: str = "tg-device-demo-key"
    demo_device_activation_code: str = "TG-ACT-8A92"
    demo_available_device_serial: str = "TG-V1.0-ESP-7B31"
    demo_available_device_key: str = "tg-device-spare-key"
    demo_available_device_activation_code: str = "TG-ACT-7B31"
    dashscope_api_key: SecretStr | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_chat_model: str = "qwen-plus"
    dashscope_medical_extraction_model: str = "qwen-vl-plus"
    dashscope_medical_report_model: str = "qwen-plus"
    dashscope_medical_prompt_version: str = "medical-records-v1"
    dashscope_timeout_seconds: float = 60.0
    dashscope_enable_search: bool = False
    medical_records_storage_dir: str = "./storage/medical_records"
    medical_records_max_upload_bytes: int = 5_000_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("dashscope_base_url", mode="before")
    @classmethod
    def normalize_dashscope_base_url(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
