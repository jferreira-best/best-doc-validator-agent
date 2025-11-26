from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.endpoints import router as api_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para validação inteligente de documentos usando LLM Vision",
    version="1.0.0"
)

# Incluir rotas
app.include_router(api_v1_router, prefix="/api/v1", tags=["Documentos"])

@app.get("/")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}