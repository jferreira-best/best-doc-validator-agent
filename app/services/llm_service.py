import json
import base64  # <--- Adicionado aqui
import binascii
from openai import AzureOpenAI, APIConnectionError, RateLimitError, BadRequestError, APITimeoutError
from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.core.exceptions import LLMProcessingError

class DocumentAnalyzerService:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            timeout=50.0 # Timeout explícito do cliente (segundos)
        )

    def _is_base64(self, s: str) -> bool:
        """Verificação rápida se a string parece ser base64 válida"""
        try:
            # Tenta decodificar e codificar de volta para ver se bate
            return base64.b64encode(base64.b64decode(s)) == s.encode()
        except Exception:
            # Se falhar a verificação estrita, deixamos passar (fail-open)
            # para a API decidir, pois algumas strings base64 podem ter padding diferente
            return True 

    def validate_document(self, image_base64: str, expected_type: str) -> dict:
        # 1. Sanity Check Básico (Economia de Recurso)
        if not image_base64 or len(image_base64) < 100:
             return {"status": "error", "message": "Imagem inválida ou corrompida (Base64 muito curto)."}

        system_prompt = PromptBuilder.build_verification_prompt(expected_type)

        try:
            response = self.client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
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

            # Validação se o filtro de conteúdo do Azure bloqueou a resposta
            if response.choices[0].finish_reason == "content_filter":
                return {
                    "status": "error", 
                    "message": "A imagem foi bloqueada pelos filtros de segurança do Azure (Conteúdo Impróprio).",
                    "data": {"detected_type": "Bloqueado"}
                }

            content = response.choices[0].message.content

            if not content:
                raise LLMProcessingError("Resposta vazia da IA")

            result_json = json.loads(content)
            
            # --- Lógica de Negócio ---
            detected_category = result_json.get("detected_type", "Outros")
            specific_name = result_json.get("specific_name", "")
            
            display_name = detected_category
            # Se caiu na vala comum ("Outros"), mas a IA leu um nome específico, usamos o nome específico.
            if detected_category.lower() == "outros" and specific_name:
                display_name = specific_name

            result_json["detected_type"] = display_name 

            expected_clean = expected_type.strip().lower()
            detected_clean = detected_category.strip().lower()
            
            is_match = False
            # Regras de validação
            if detected_clean == expected_clean: is_match = True
            elif expected_clean == "outros": is_match = True
            elif result_json.get("is_match") is True: is_match = True

            return {
                "status": "success" if is_match else "error",
                "message": "Documento validado" if is_match else "Tipo de documento errado",
                "data": result_json
            }

        # --- TRATAMENTO DE ERROS ESPECÍFICOS DO AZURE ---

        except RateLimitError:
            return {
                "status": "error", 
                "message": "O sistema está sobrecarregado (Rate Limit Azure). Tente novamente em alguns segundos.",
                "data": {"detected_type": "Erro Sistema"}
            }

        except BadRequestError as e:
            # Erro 400: Filtro de Conteúdo ou Imagem Inválida
            error_code = getattr(e, 'code', '')
            if error_code == 'content_filter':
                msg = "Imagem rejeitada pela política de segurança (Responsible AI)."
            else:
                msg = f"Erro na requisição à IA: {e.message}"
            
            return {"status": "error", "message": msg, "data": {"detected_type": "Erro"}}

        except APITimeoutError:
            return {
                "status": "error", 
                "message": "A análise demorou muito e excedeu o tempo limite.",
                "data": {"detected_type": "Timeout"}
            }

        except APIConnectionError:
            return {
                "status": "error", 
                "message": "Falha de conexão com o serviço Azure OpenAI.",
                "data": {"detected_type": "Erro Conexão"}
            }

        except json.JSONDecodeError:
            return {"status": "error", "message": "A IA retornou um formato inválido.", "data": {"detected_type": "Erro Parse"}}

        except Exception as e:
            return {"status": "error", "message": f"Erro interno não tratado: {str(e)}", "data": {"detected_type": "Erro Crítico"}}