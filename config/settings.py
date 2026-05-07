"""
Cấu hình chung cho dự án VN-Legal-Bench-Dataset.
Load từ .env file.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database
    DB_NAME: str = "vn_legal_bench"
    DB_USER: str = "legal"
    DB_PASSWORD: str = "legal123"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # Special IDs
    CONSTITUTION_ID: str = "HP2013"

    # LLM API Keys
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    NINEROUTER_API_KEY: str = ""
    NINEROUTER_BASE_URL: str = "http://localhost:20128/v1"
    LLM_MODEL: str = "llama3" # Model mặc định

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    BENCHMARK_DIR: Path = BASE_DIR / "data" / "benchmark"

    # Chrome Automation
    CHROME_PATH: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    CHROME_USER_DATA_DIR: str = r"C:\ChromeDebug"
    CHROME_DEBUG_PORT: int = 9222

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
