import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Configurações do Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_KEY: str
    AZURE_OPENAI_DEPLOYMENT: str  # ex: gpt-4o-mini-deploy
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview" # Versão recomendada para Vision

    # Configurações Gerais
    PORT: int = 8000
    PROJECT_NAME: str = "DocValidator Agent (Azure)"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True,
        extra="ignore"
    )

settings = Settings()