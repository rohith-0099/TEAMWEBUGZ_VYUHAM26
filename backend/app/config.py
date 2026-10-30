"""Settings read from the environment / .env (contracts §10). Owner: Backend Core."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://trinetra:trinetra@localhost:5432/trinetra"
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_extract_model: str = ""
    llm_verify_model: str = ""
    llm_concurrency: int = 8
    mapping_confidence_threshold: float = 0.6
    firecrawl_api_key: str = ""
    n8n_webhook_url: str = ""
    attack_version: str = "20.0"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    cors_origins: str = "http://localhost:3000"
    geoip_db_path: str = "/data/dbip-city-lite.mmdb"


settings = Settings()
