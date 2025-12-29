"""Configuration management using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./data/app.db"
    
    # Directories
    credentials_dir: str = "./credentials"
    data_dir: str = "./data"
    
    # CORS
    allowed_origins: list[str] = ["*"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    
    # Application
    app_name: str = "CV Email Sender API"
    app_version: str = "1.0.0"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def get_credentials_path(self, user_id: int) -> str:
        """Get credentials file path for user."""
        return f"{self.credentials_dir}/user_{user_id}_credentials.json"
    
    def get_token_path(self, user_id: int) -> str:
        """Get token file path for user."""
        return f"{self.credentials_dir}/user_{user_id}_token.json"
    
    def get_resume_path(self, user_id: int) -> str:
        """Get resume file path for user."""
        return f"{self.data_dir}/user_{user_id}_resume.pdf"


# Global settings instance
settings = Settings()

