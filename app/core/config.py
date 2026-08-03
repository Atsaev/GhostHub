from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GhostHub"
    debug: bool = False

    database_host: str
    database_port: int = 5432
    database_name: str
    database_user: str
    database_password: str

    storage_path: str = "storage"

    room_ttl_seconds: int = 3600
    room_max_devices: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

# тянем из env с pydantic-settings
settings = Settings()  # type: ignore
