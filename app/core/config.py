from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GhostHub"
    debug: bool = False

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# тянем из env с pydantic-settings
settings = Settings()  # type: ignore
