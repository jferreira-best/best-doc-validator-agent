import json
import base64
import re
import io
from pypdf import PdfReader
from docx import Document
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI, APIConnectionError, RateLimitError, BadRequestError, APITimeoutError
from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.core.exceptions import LLMProcessingError

class DocumentAnalyzerService:
    # --- CONSTANTES DE CONFIGURAÇÃO ---
    MAX_FILE_SIZE_MB = 15
    MAX_TEXT_LENGTH = 20000  # Limita o texto enviado à LLM para economizar tokens
    
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

    def _validate_file_integrity(self, file_data: bytes, extension: str) -> dict:
        """Verifica tamanho e assinatura binária para evitar arquivos maliciosos."""
        # 1. Validação de Tamanho
        if len(file_data) > (self.MAX_FILE_SIZE_MB * 1024 * 1024):
            return {"valid": False, "error": f"O arquivo excede o limite de {self.MAX_FILE_SIZE_MB}MB."}

        # 2. Validação de Assinatura (Magic Number)
        header = file_data[:4]
        expected_header = self.MAGIC_NUMBERS.get(extension)
        
        if expected_header and not file_data.startswith(expected_header):
            # Exceção para DOCX/XLSX que são ZIPs (iniciam com PK)
            if extension in ['docx'] and file_data.startswith(b'PK'):
                return {"valid": True}
            return {"valid": False, "error": f"O arquivo diz ser '.{extension}' mas o conteúdo não corresponde (Cabeçalho inválido)."}
            
        return {"valid": True}

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
        """
        Extrai texto de PDF. Retorna (Texto, Erro).
        Lida com Senhas e PDFs Escaneados (extraindo imagens internas).
        """
        text_content = ""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            
            # 1. Checagem de Senha
            if reader.is_encrypted:
                return "", "PDF_PASSWORD_PROTECTED"

            # 2. Extração de Texto Nativo
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + " "
            
            # 3. Fallback para PDF Escaneado (Se tiver muito pouco texto)
            if len(text_content.strip()) < 50:
                print("PDF Escaneado detectado. Iniciando OCR nas imagens internas...")
                for page in reader.pages:
                    if hasattr(page, 'images') and page.images:
                        for image in page.images:
                            try:
                                # image.data são os bytes da imagem dentro do PDF
                                ocr_text = self._extract_text_cloud(image.data)
                                text_content += ocr_text + " "
                            except:
                                pass # Ignora imagens internas corrompidas
                            
            return text_content, None
        except Exception as e:
            print(f"Erro PDF Genérico: {e}")
            return "", "PDF_CORRUPTED"

    def _extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Lê arquivos Word (.docx)."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception:
            return ""

    def _apply_regex_rules(self, text: str) -> str:
        """Filtro Rápido via Regex (Economia de Custo)."""
        text_clean = " ".join(text.split())
        patterns = {
            "Comprovante de Seguro Desemprego": r"(?i)(PARSEGDES|PAR[5s]EGDE[5s]|PAR\s+SEG\s+DES|SEGURO\s+DESEMPREGO|PARC\s+BENEF\s+MTE)",
            "Carteira de Trabalho": r"(?i)(carteira\s+de\s+trabalho|dataprev|minist[ée]rio\s+do\s+traba[l1]ho|s[ée]rie\s*\d{3,}|p[o0]legar)",
            "Comprovante de Residência": r"(?i)(claro|vivo|tim|oi|enel|sabesp|embasa|light|cpfl|corsan|caern|energisa|copasa).{0,300}?(venciment[o0]|nota\s+fisca[l1]|total|fatura|medidor|leitura)",
            "CPF": r"(?i)(cpf|cic|cadastro\s+de\s+pessoas?\s+f[íi]sicas)",
            "RG": r"(?i)(registro\s+geral|c[ée]dula\s+de\s+identidade|ssp|secretaria\s+de\s+seguran[çc]a)",
            
            # Regex Expandido para Investimentos/Poupança
            "Extrato Poupança ou Aplicação": r"(?i)(poup[aã]n[çc]a|aplica[çc][ãa]o\s+autom[áa]tica|rendimento\s+bruto|resgate\s+autom[áa]tico|investimento|CDB|RDB|fundo\s+de\s+investimento)",
            "Extrato Bancário": r"(?i)(extrato\s+de\s+movimenta[çc][ãa]o|saldo\s+dispon[íi]vel|conta\s+corrente|b[o0]lsa\s+fam[íi1]lia|caixa\s+tem)"
        }
        for doc_type, regex in patterns.items():
            if re.search(regex, text_clean): return doc_type
        return None

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
        
        integrity_check = self._validate_file_integrity(file_data, extension)
        if not integrity_check["valid"]:
             return {"status": "error", "message": f"Arquivo rejeitado por segurança: {integrity_check.get('error')}"}

        # --- 2. Extração de Conteúdo ---
        extracted_text = ""
        is_image = False
        error_flag = None

        if extension == 'pdf':
            extracted_text, error_flag = self._extract_text_from_pdf(file_data)
            # Tratamento de Erros Específicos de PDF
            if error_flag == "PDF_PASSWORD_PROTECTED":
                return {"status": "error", "message": "O PDF está protegido por senha. Por favor, remova a senha e tente novamente."}
            if error_flag == "PDF_CORRUPTED":
                return {"status": "error", "message": "O arquivo PDF parece estar corrompido ou ilegível."}
                
        elif extension in ['docx', 'doc']:
            extracted_text = self._extract_text_from_docx(file_data)
        else:
            is_image = True # JPG, PNG
            extracted_text = self._extract_text_cloud(file_data)

        # --- 3. Fase Regex (Rápida e Barata) ---
        if extracted_text:
            detected_regex = self._apply_regex_rules(extracted_text)
            if detected_regex:
                expected_clean = expected_type.lower()
                detected_clean = detected_regex.lower()
                
                # Verifica match flexível
                if expected_clean in detected_clean or detected_clean in expected_clean:
                    return {
                        "status": "success",
                        "message": "Validado via Regras (Rápido).",
                        "data": {
                            "detected_type": detected_regex,
                            "is_match": True,
                            "method": "text_extraction_regex",
                            "confidence": "high",
                            "step_1_extract_snippet": extracted_text[:100]
                        }
                    }

        # --- 4. Fase LLM (Inteligência Artificial) ---
        
        # Truncamento (Economia de Tokens)
        if len(extracted_text) > self.MAX_TEXT_LENGTH:
            extracted_text = extracted_text[:self.MAX_TEXT_LENGTH] + "\n...[Texto truncado para análise]..."

        system_prompt = PromptBuilder.build_verification_prompt(expected_type)
        user_content = []

        if is_image:
            user_content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{file_base64}", "detail": "high"}}]
        else:
            if not extracted_text or len(extracted_text.strip()) < 10:
                extracted_text = "AVISO: Não foi possível extrair texto legível deste documento digital."
            user_content = [{"type": "text", "text": f"Conteúdo extraído ({extension}):\n\n{extracted_text}"}]

        try:
            response = self.llm_client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                max_tokens=300, temperature=0.0, response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if not content: raise LLMProcessingError("Resposta vazia da IA")
            
            result_json = json.loads(content)
            result_json["method"] = "azure_llm_visual" if is_image else "azure_llm_text"
            result_json["file_type"] = extension

            # Validação Final de Match
            is_match = result_json.get("is_match", False)
            detected = result_json.get("detected_type", "").lower()
            expected = expected_type.lower()
            
            if detected == expected or expected == "outros" or is_match:
                is_match = True

            return {"status": "success" if is_match else "error", "message": "Validado" if is_match else "Inválido", "data": result_json}

        # --- TRATAMENTO DE ERROS (Robustez) ---
        except RateLimitError:
            return {"status": "error", "message": "O sistema está temporariamente ocupado (Rate Limit). Tente novamente em breve.", "data": {"detected_type": "Erro Sistema"}}
        
        except BadRequestError as e:
            # Tratamento para Prompt Injection / Filtros de Segurança da Azure
            error_str = str(e)
            if "content_filter" in error_str or "ResponsibleAIPolicyViolation" in error_str:
                return {
                    "status": "error", 
                    "message": "⛔ SEGURANÇA: O documento contém conteúdo suspeito ou tentativas de manipulação da IA (Bloqueado pelo Azure AI).",
                    "data": {"detected_type": "Bloqueio de Segurança"}
                }
            return {"status": "error", "message": f"Erro na requisição à IA: {e.message}", "data": {"detected_type": "Erro"}}

        except APITimeoutError:
            return {"status": "error", "message": "Timeout na análise da IA.", "data": {"detected_type": "Timeout"}}

        except Exception as e:
            return {"status": "error", "message": f"Erro Interno não tratado: {str(e)}", "data": {}}