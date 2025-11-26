from pydantic import BaseModel, Field
from typing import Optional, Literal

class DocumentRequest(BaseModel):
    expected_type: str = Field(..., description="Tipo esperado (ex: RG)")
    image_base64: str = Field(..., description="Base64 da imagem")

class DocumentResponse(BaseModel):
    status: Literal["success", "error"]
    message: str
    detected_type: str
    confidence: Optional[str] = None
    reasoning: Optional[str] = None