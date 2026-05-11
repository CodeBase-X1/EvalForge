"""Central configuration — loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # Phoenix
    phoenix_endpoint: str = "http://localhost:6006"
    phoenix_api_key: str = ""

    # EvalForge pipeline
    evalforge_trace_limit: int = 500
    evalforge_failure_threshold: float = 0.5
    evalforge_num_clusters: int = 0          # 0 = auto-detect
    evalforge_cases_per_cluster: int = 10
    evalforge_output_dir: str = "./output"

    # UI
    evalforge_ui_host: str = "0.0.0.0"
    evalforge_ui_port: int = 8000


# Singleton — import this everywhere
settings = Settings()
