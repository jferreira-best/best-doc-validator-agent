import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Configurações do Azure OpenAI (LLM)
    AZURE_OPENAI_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # --- NOVOS CAMPOS (Correção do Erro) ---
    # Configurações do Azure Computer Vision (OCR)
    AZURE_CV_KEY: str
    AZURE_CV_ENDPOINT: str

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Permite que variáveis extras no ambiente não quebrem a aplicação
        extra = "ignore" 

settings = Settings()