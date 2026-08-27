from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # asynch speaks the native ClickHouse protocol (port 9000), not the
    # HTTP interface (8123). The agent's CLICKHOUSE_URL=http://... form does
    # not work with asynch — these fields are passed to Connection as kwargs.
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "voice"
    clickhouse_table: str = "voice.turns"

    audio_s3_bucket: str = ""
    audio_s3_region: str = "us-west-1"

    page_size_default: int = 50
    page_size_max: int = 200
    presigned_url_ttl: int = 3600


settings = Settings()
