"""Configuration management using Pydantic Settings."""

import glob as glob_module

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
    app_name: str = "Cender API"
    app_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    def get_credentials_path(self, user_id: int) -> str:
        """Get credentials file path for user."""
        return f"{self.credentials_dir}/user_{user_id}_credentials.json"

    def get_token_path(self, user_id: int) -> str:
        """Get token file path for user."""
        return f"{self.credentials_dir}/user_{user_id}_token.json"

    def get_user_data_dir(self, user_id: int) -> str:
        """Get user-specific data directory."""
        return f"{self.data_dir}/user_{user_id}"

    def get_resume_path(self, user_id: int) -> str | None:
        """
        Get resume file path for user.

        Returns the first PDF found in the user's data directory, or None if not found.
        """
        user_dir = self.get_user_data_dir(user_id)
        pdf_files = glob_module.glob(f"{user_dir}/*.pdf")
        return pdf_files[0] if pdf_files else None


# Global settings instance
settings = Settings()
