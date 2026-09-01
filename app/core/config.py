from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "GhostHub"
    debug: bool = False

    # префикс пути при деплое за обратным прокси (например "/ghost");
    # пустая строка — без префикса
    base_path: str = ""

    # database_host: str
    # database_port: int = 5432
    # database_name: str
    # database_user: str
    # database_password: str
    database_url: str

    storage_path: str = "storage"

    room_ttl_seconds: int = 3600
    room_max_devices: int = 5
    room_max_bytes: int = 150 * 1024 * 1024
    room_cleanup_interval_seconds: int = 60

    # rate-limit
    rate_limit_create_rooms: int = 20
    rate_limit_create_window_seconds: int = 3600
    rate_limit_join_attempts: int = 10
    rate_limit_join_window_seconds: int = 900

    # секрет для подписи cookie доступа к комнатам
    secret_key: str = "dev-secret-change-me"

    # абсолютный базовый url для ссылок и qr-кодов (если приложение за прокси)
    public_base_url: str = ""

    # stun-сервер для webrtc p2p
    p2p_stun_url: str = "stun:stun.l.google.com:19302"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("base_path")
    @classmethod
    def _normalize_base_path(cls, value: str) -> str:
        return value.rstrip("/")


# тянем из env с pydantic-settings
settings = Settings()  # type: ignore
