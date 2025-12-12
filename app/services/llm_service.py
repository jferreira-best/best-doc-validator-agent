import json
import base64
import re
import io
import unicodedata
from pypdf import PdfReader
from docx import Document
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI, APIConnectionError, RateLimitError, BadRequestError, APITimeoutError
from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.core.exceptions import LLMProcessingError
import unicodedata

class DocumentAnalyzerService:
    # --- CONSTANTES DE CONFIGURAÇÃO ---
    MAX_FILE_SIZE_MB = 15
    MAX_TEXT_LENGTH = 25000  # Limita o texto enviado à LLM para economizar tokens
    
    # Assinaturas Binárias (Magic Numbers) para validação de segurança
    MAGIC_NUMBERS = {
        'pdf': b'%PDF',
        'jpg': b'\xff\xd8',
        'jpeg': b'\xff\xd8',
        'png': b'\x89PNG',
        'docx': b'PK',  # Arquivos Office Open XML são Zips
        'doc': b'\xd0\xcf\x11\xe0' # Formato OLE antigo
    }

    def __init__(self):
        # Cliente para Inteligência Artificial (GPT-4o)
        self.llm_client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            timeout=60.0 
        )
        # Cliente para OCR (Visão Computacional)
        self.ocr_client = ImageAnalysisClient(
            endpoint=settings.AZURE_CV_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_CV_KEY)
        )

    def _normalize_text(self, text: str) -> str:
        """
        Remove acentos e coloca em minúsculas para comparação segura.
        Ex: 'Comprovante de Residência' -> 'comprovante de residencia'
        """
        if not text: return ""
        # Normaliza para decompor caracteres (ex: 'ê' vira 'e' + '^')
        nfkd_form = unicodedata.normalize('NFKD', str(text))
        # Filtra apenas caracteres não-diacríticos (remove os acentos) e converte para minúsculo
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

    def _validate_file_integrity(self, file_data: bytes, extension: str) -> dict:
        """
        Verifica tamanho e assinatura binária (Magic Numbers).
        
        AJUSTE DE SEGURANÇA (CROSS-TYPE):
        Permite que a extensão não bata exatamente com o conteúdo (ex: PNG renomeado para JPG),
        DESDE QUE o conteúdo seja de um formato aceito na lista segura.
        """
        # 1. Validação de Tamanho
        if len(file_data) > (self.MAX_FILE_SIZE_MB * 1024 * 1024):
            return {"valid": False, "error": f"O arquivo excede o limite de {self.MAX_FILE_SIZE_MB}MB."}

        # 2. Validação Estrita de Magic Numbers (Ideal)
        header = file_data[:4]
        expected_header = self.MAGIC_NUMBERS.get(extension)
        
        # Se bater exatamente com a extensão, ótimo.
        if expected_header and file_data.startswith(expected_header):
            return {"valid": True}
            
        # 3. Validação Flexível (Fallback Seguro)
        # Se não bateu com a extensão, verificamos se é ALGUM outro formato permitido.
        # Isso permite salvar PNG como JPG sem erro.
        is_safe_format = False
        
        for fmt, magic in self.MAGIC_NUMBERS.items():
            if file_data.startswith(magic):
                is_safe_format = True
                break
        
        if is_safe_format:
            # Arquivo é seguro (é uma imagem ou PDF válido), mesmo com extensão errada.
            return {"valid": True}

        # Se chegou aqui, o arquivo tem um header desconhecido (ex: EXE, SH, BAT)
        return {
            "valid": False, 
            "error": f"O arquivo possui uma assinatura inválida. Extensão diz '.{extension}', mas o conteúdo não é reconhecido como imagem ou PDF."
        }

    def _extract_text_cloud(self, image_bytes: bytes) -> str:
        """Usa Azure Vision para OCR de alta precisão em imagens."""
        try:
            result = self.ocr_client.analyze(
                image_data=image_bytes,
                visual_features=[VisualFeatures.READ]
            )
            if result.read:
                return " ".join([line.text for block in result.read.blocks for line in block.lines])
            return ""
        except Exception as e:
            print(f"Aviso OCR Azure: {e}")
            return ""

    def _extract_text_from_pdf(self, file_bytes: bytes) -> tuple[str, str]:
        """Extrai texto de PDF de forma híbrida e robusta."""
        text_content = ""
        images_found = False
        
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    return "", "PDF_PASSWORD_PROTECTED"

            for page in reader.pages:
                try:
                    extracted = page.extract_text()
                    if extracted:
                        text_content += extracted + "\n"
                except:
                    pass
                
                try:
                    if hasattr(page, 'images') and page.images:
                        for image in page.images:
                            images_found = True
                            ocr_text = self._extract_text_cloud(image.data)
                            if ocr_text:
                                text_content += f"\n[CONTEÚDO DE IMAGEM OCR]: {ocr_text}\n"
                except:
                    pass 
            
            if not text_content.strip():
                if not images_found:
                    return "", "PDF_EMPTY_CONTENT"
                return "", "PDF_NO_TEXT_FOUND"
                            
            return text_content, None

        except Exception as e:
            if "password" in str(e).lower():
                return "", "PDF_PASSWORD_PROTECTED"
            print(f"Erro PDF Genérico: {e}")
            return "", "PDF_CORRUPTED"
        
    def _is_legible_text(self, text: str, is_image: bool) -> bool:
        """Heurística simples para decidir se o texto extraído é legível."""
        if not text: return False
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean: return False

        min_len = 80 if is_image else 40
        if len(clean) < min_len: return False

        words = re.split(r"\W+", clean)
        meaningful = [w for w in words if len(w) >= 3]
        min_words = 10 if is_image else 5
        if len(meaningful) < min_words: return False

        return True

    def _extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Lê arquivos Word (.docx)."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception:
            return ""

    def _audit_negative_results(self, result_json: dict) -> tuple[bool, str]:
        """Auditoria de Segurança: Verifica se o documento é um 'Nada Consta' ou 'Vazio'."""
        reasoning = str(result_json.get("reasoning", "")).lower()
        message = str(result_json.get("message", "")).lower()
        
        negative_terms = [
            "não há informe", "não existe", "nada consta", 
            "ausência de dados", "nenhum registro", "sem dados",
            "declaração não entregue", "não foram encontrados"
        ]
        
        for term in negative_terms:
            if term in reasoning or term in message:
                return False, f"Documento indica ausência de dados: '{term}'."
                
        if result_json.get("result") == "INVALID":
            return False, result_json.get("reasoning", "Documento inválido.")
            
        return True, "OK"

    def _normalize_text(self, text: str) -> str:
        """Remove acentos e coloca em minúsculas para comparação segura."""
        if not text: return ""
        # Normaliza para decompor caracteres (ex: 'ê' vira 'e' + '^')
        nfkd_form = unicodedata.normalize('NFKD', str(text))
        # Filtra apenas caracteres não-diacríticos (remove os acentos) e converte para minúsculo
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()


    def validate_document(self, file_base64: str, expected_type: str, file_name: str = "arquivo.jpg") -> dict:
        # --- 1. Validações de Entrada ---
        if not file_base64 or len(file_base64) < 100:
             return {"status": "error", "message": "Arquivo inválido ou vazio."}

        try:
            file_data = base64.b64decode(file_base64)
        except:
            return {"status": "error", "message": "Falha na decodificação do arquivo (Base64 corrompido)."}

        # Identificação de Extensão e Segurança
        extension = file_name.split('.')[-1].lower()
        if extension == 'jpeg': extension = 'jpg'
        
        # Validação de integridade (Agora permite extensão trocada se o arquivo for seguro)
        integrity_check = self._validate_file_integrity(file_data, extension)
        if not integrity_check["valid"]:
             return {"status": "error", "message": f"Arquivo rejeitado: {integrity_check.get('error')}"}

        # --- 2. Extração de Conteúdo ---
        extracted_text = ""
        is_image = False
        error_flag = None

        if extension == 'pdf':
            extracted_text, error_flag = self._extract_text_from_pdf(file_data)
            if error_flag:
                msg_map = {
                    "PDF_PASSWORD_PROTECTED": "PDF protegido por senha.",
                    "PDF_EMPTY_CONTENT": "PDF vazio ou ilegível.",
                    "PDF_CORRUPTED": "PDF corrompido."
                }
                return {"status": "error", "message": msg_map.get(error_flag, "Erro ao ler PDF.")}
                
        elif extension in ['docx', 'doc']:
            extracted_text = self._extract_text_from_docx(file_data)
        else:
            is_image = True # JPG, PNG
            extracted_text = self._extract_text_cloud(file_data)

        # Check de Legibilidade Global
        if not self._is_legible_text(extracted_text, is_image):
            return {
                "status": "error",
                "message": "Qualidade Insuficiente: Não foi possível ler o conteúdo. Imagem borrada ou escura.",
                "data": {"detected_type": "Ilegível", "reasoning": "Texto insuficiente."}
            }

        if str(expected_type).lower() == "outros":
            return {
                "status": "success",
                "message": "Documento aceito como 'Outros'.",
                "data": {"detected_type": "Outros", "is_match": True}
            }

        # --- 3. Chamada LLM ---
        if len(extracted_text) > self.MAX_TEXT_LENGTH:
            extracted_text = extracted_text[:self.MAX_TEXT_LENGTH] + "\n...[Truncado]..."

        system_prompt = PromptBuilder.build_verification_prompt(expected_type)
        
        user_content = []
        if is_image:
            user_content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{file_base64}", "detail": "high"}}]
        else:
            user_content = [{"type": "text", "text": f"Conteúdo extraído ({extension}):\n\n{extracted_text}"}]

        try:
            response = self.llm_client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                max_tokens=300, temperature=0.0, response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result_json = json.loads(content)
            result_json["method"] = "azure_llm_visual" if is_image else "azure_llm_text"
            result_json["file_type"] = extension

            # Auditoria de Nada Consta
            is_safe, safe_reason = self._audit_negative_results(result_json)
            if not is_safe:
                return {"status": "error", "message": f"Reprovado: {safe_reason}", "data": result_json}

            # --- 4. VALIDAÇÃO DE TIPOS E SINÔNIMOS (CORREÇÃO FINAL) ---
            detected_raw = str(result_json.get("detected_type", ""))
            
            # Normaliza ambos (remove acentos, minúsculo)
            detected_norm = self._normalize_text(detected_raw)
            expected_norm = self._normalize_text(str(expected_type))

            # Mapa de Sinônimos (Resolver 'Endereço vs Residência' e 'Holerite vs Contracheque')
            synonym_map = {
                "endereco": "residencia",
                "residencia": "residencia",
                "contracheque": "holerite",
                "holerite": "holerite"
            }

            # Substitui sinônimos nas strings normalizadas
            for term, canonical in synonym_map.items():
                if term in expected_norm: 
                    expected_norm = expected_norm.replace(term, canonical)
                if term in detected_norm: 
                    detected_norm = detected_norm.replace(term, canonical)

            # Lógica de Match
            ai_match = result_json.get("is_match", False)
            type_matches = (expected_norm in detected_norm) or (detected_norm in expected_norm)

            if ai_match and not type_matches:
                # Só reprova se, mesmo após normalizar sinônimos, ainda for diferente (Ex: RG vs CPF)
                final_status = "error"
                final_msg = f"Documento incorreto. Você enviou um '{detected_raw}', mas era esperado um '{expected_type}'."
            
            elif ai_match:
                # Se IA deu OK e os tipos batem (ou são sinônimos)
                final_status = "success"
                final_msg = "Validado com Sucesso"
                
            else:
                final_status = "error"
                final_msg = f"Reprovado: {result_json.get('reasoning', 'Documento não atende aos requisitos.')}"

            return {"status": final_status, "message": final_msg, "data": result_json}

        except Exception as e:
            return {"status": "error", "message": f"Erro Interno: {str(e)}", "data": {}}