from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


def _environment(value: str) -> str:
    return {"development": "dev", "production": "prod"}.get(value.lower(), value.lower())


@dataclass(frozen=True)
class MealbotSettings:
    environment: str
    app_base_url: str
    upload_dir: str
    database_url: str
    wecom_corp_id: str
    wecom_agent_id: str
    wecom_secret: str
    wecom_token: str
    wecom_encoding_aes_key: str
    reminder_worker_interval_seconds: int
    media_worker_interval_seconds: int
    release_check_strict: bool
    benchmark_admissions_blocking: bool
    benchmark_mealbot_blocking: bool

    def validation_errors(self) -> list[str]:
        if self.environment not in {"staging", "prod"}:
            return []
        required = {
            "DATABASE_URL": self.database_url,
            "APP_BASE_URL": self.app_base_url,
            "WECOM_CORP_ID": self.wecom_corp_id,
            "WECOM_AGENT_ID": self.wecom_agent_id,
            "WECOM_SECRET": self.wecom_secret,
            "WECOM_TOKEN": self.wecom_token,
            "WECOM_ENCODING_AES_KEY": self.wecom_encoding_aes_key,
        }
        errors = [f"{name} is required" for name, value in required.items() if not value]
        if self.environment == "prod" and self.app_base_url:
            parsed = urlparse(self.app_base_url)
            hostname = (parsed.hostname or "").lower()
            placeholders = {"example.com", "school.example.com", "your-domain.com", "localhost", "127.0.0.1"}
            if parsed.scheme != "https" or hostname in placeholders or hostname.endswith(".example.com"):
                errors.append("APP_BASE_URL must be an externally reachable HTTPS origin in production")
        return errors

    def safe_summary(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "app_base_url": self.app_base_url,
            "upload_dir": self.upload_dir,
            "database_configured": bool(self.database_url),
            "wecom_corp_id_configured": bool(self.wecom_corp_id),
            "wecom_agent_id_configured": bool(self.wecom_agent_id),
            "wecom_secret_configured": bool(self.wecom_secret),
            "wecom_callback_configured": bool(self.wecom_token and self.wecom_encoding_aes_key),
            "reminder_worker_interval_seconds": self.reminder_worker_interval_seconds,
            "media_worker_interval_seconds": self.media_worker_interval_seconds,
        }


def _bool(raw: str, default: bool = False) -> bool:
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def load_settings(environ: Mapping[str, str] | None = None) -> MealbotSettings:
    env = os.environ if environ is None else environ
    app_env = env.get("ENVIRONMENT", env.get("GAOKAO_ENV", "dev"))
    return MealbotSettings(
        environment=_environment(app_env),
        app_base_url=env.get("APP_BASE_URL", "http://localhost:8787"),
        upload_dir=env.get("UPLOAD_DIR", str(Path(__file__).resolve().parents[3] / "uploads")),
        database_url=env.get("DATABASE_URL", env.get("DATABASE_URL_ADMIN", "")),
        wecom_corp_id=env.get("WECOM_CORP_ID", ""),
        wecom_agent_id=env.get("WECOM_AGENT_ID", ""),
        wecom_secret=env.get("WECOM_SECRET", env.get("WECOM_APP_SECRET", "")),
        wecom_token=env.get("WECOM_TOKEN", ""),
        wecom_encoding_aes_key=env.get("WECOM_ENCODING_AES_KEY", ""),
        reminder_worker_interval_seconds=int(env.get("REMINDER_WORKER_INTERVAL_SECONDS", "5")),
        media_worker_interval_seconds=int(env.get("MEDIA_WORKER_INTERVAL_SECONDS", "5")),
        release_check_strict=_bool(env.get("RELEASE_CHECK_STRICT", "false")),
        benchmark_admissions_blocking=_bool(env.get("BENCHMARK_ADMISSIONS_BLOCKING", "false")),
        benchmark_mealbot_blocking=_bool(env.get("BENCHMARK_MEALBOT_BLOCKING", "true"), True),
    )


_SETTINGS = load_settings()

DATABASE_URL = _SETTINGS.database_url

APP_BASE_URL = _SETTINGS.app_base_url

UPLOAD_DIR = _SETTINGS.upload_dir

WECOM_CORP_ID = _SETTINGS.wecom_corp_id
WECOM_AGENT_ID = _SETTINGS.wecom_agent_id
WECOM_SECRET = _SETTINGS.wecom_secret
WECOM_TOKEN = _SETTINGS.wecom_token
WECOM_ENCODING_AES_KEY = _SETTINGS.wecom_encoding_aes_key

ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024)))

ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    **ALLOWED_IMAGE_TYPES,
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
