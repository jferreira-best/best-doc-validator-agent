from fastapi import APIRouter, HTTPException
from app.schemas.document import DocumentRequest, DocumentResponse
from app.services.llm_service import DocumentAnalyzerService

router = APIRouter()
document_service = DocumentAnalyzerService()

@router.post("/validate", response_model=DocumentResponse)
async def validate_document_endpoint(payload: DocumentRequest):
    """
    Endpoint para validação de documentos via imagem.
    """
    if not payload.image_base64:
        raise HTTPException(status_code=400, detail="Imagem não fornecida")

    result = document_service.validate_document(
        image_base64=payload.image_base64,
        expected_type=payload.expected_type
    )
    
    # Mapeamento do retorno do serviço para o Schema de Resposta
    # Note que 'data' vem do serviço contendo 'detected_type', 'reasoning', etc.
    data = result.get("data", {})
    
    return DocumentResponse(
        status=result["status"],
        message=result["message"],
        detected_type=data.get("detected_type", "Desconhecido"),
        confidence=data.get("confidence"),
        reasoning=data.get("reasoning")
    )