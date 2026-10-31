"""Settings read from the environment / .env (contracts §10). Owner: Backend Core."""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://trinetra:trinetra@localhost:5432/trinetra"
    llm_api_key: str = ""              # fallback key for any provider without its own key below
    gemini_api_key: str = ""           # used for models named "gemini/..."
    groq_api_key: str = ""             # used for models named "groq/..."
    llm_api_base: str = ""
    llm_extract_model: str = ""
    llm_verify_model: str = ""
    llm_concurrency: int = 8
    llm_cache: bool = True             # false only to measure real latency
    llm_tokens_per_minute: int = 0     # TPM limit for any provider without its own setting; 0 = none
    llm_tpm_gemini: int | None = None  # Gemini tokens-per-minute limit; empty = no client-side pacing
    llm_tpm_groq: int | None = None    # Groq tokens-per-minute limit; empty = no client-side pacing
    llm_rpm_gemini: int | None = None  # Gemini requests-per-minute limit; empty = none
    llm_rpm_groq: int | None = None    # Groq requests-per-minute limit; empty = none
    mapping_confidence_threshold: float = 0.6
    firecrawl_api_key: str = ""
    n8n_webhook_url: str = ""
    attack_version: str = "20.0"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    cors_origins: str = "http://localhost:3000"
    nvd_api_key: str = ""
    ocr_enabled: bool = True               # read text from report images with Tesseract (no LLM)
    geoip_db_path: str = "/data/dbip-city-lite.mmdb"


    @field_validator("llm_tpm_gemini", "llm_tpm_groq", "llm_rpm_gemini", "llm_rpm_groq", mode="before")
    @classmethod
    def _empty_is_none(cls, value):
        # An empty LLM_TPM_* line (or one holding only an inline comment) means "no limit".
        if isinstance(value, str) and (not value.strip() or value.strip().startswith("#")):
            return None
        return value

    @property
    def llm_enabled(self) -> bool:
        """False = offline mock mode: no key for any provider."""
        return bool(self.llm_api_key or self.gemini_api_key or self.groq_api_key)


settings = Settings()
