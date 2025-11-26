import json
from openai import AzureOpenAI  # <--- MUDANÇA IMPORTANTE
from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.core.exceptions import LLMProcessingError

class DocumentAnalyzerService:
    def __init__(self):
        # Inicializa o cliente específico para Azure
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )

    def validate_document(self, image_base64: str, expected_type: str) -> dict:
        system_prompt = PromptBuilder.build_verification_prompt(expected_type)

        try:
            response = self.client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "high"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=300,
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMProcessingError("Resposta vazia da IA")

            result_json = json.loads(content)
            
            detected = result_json.get("detected_type", "Outros")
            
            # --- LÓGICA DE VALIDAÇÃO (GUARDRAIL) ---
            
            detected_clean = detected.strip().lower()
            expected_clean = expected_type.strip().lower()
            
            is_match = False

            # Regra 1: Se bater exatamente o que pediu (ex: pediu RG, veio RG)
            if detected_clean == expected_clean:
                is_match = True
            
            # Regra 2 (O CORINGA): Se o usuário selecionou "Outros", aceitamos TUDO.
            # A IA vai dizer o que é (ex: CNH), mas o status será OK.
            elif expected_clean == "outros":
                is_match = True
                
            # Regra 3: Fallback da IA (se a própria IA já marcou match no JSON interno)
            elif result_json.get("is_match") is True:
                is_match = True

            if is_match:
                return {
                    "status": "success",
                    "message": "Documento validado com sucesso",
                    "data": result_json
                }
            else:
                return {
                    "status": "error",
                    "message": "Tipo de documento errado",
                    "data": result_json
                }

        except json.JSONDecodeError:
            raise LLMProcessingError("Falha ao decodificar JSON da IA")
        except Exception as e:
            return {"status": "error", "message": f"Erro interno (Azure): {str(e)}", "data": {}}