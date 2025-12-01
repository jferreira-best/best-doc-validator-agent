import azure.functions as func
import logging
import json
from app.services.llm_service import DocumentAnalyzerService

# Inicializa o App da Function
app = func.FunctionApp()

@app.route(route="validate_document", auth_level=func.AuthLevel.FUNCTION)
def validate_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Requisição recebida: Validação de Documento (Híbrida/Segura).')

    try:
        # 1. Parse e Validação do JSON de Entrada
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({
                    "result": "NOK", 
                    "message": "O corpo da requisição deve ser um JSON válido."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # 2. Extração de Parâmetros
        # Aceita 'file_base64' (novo padrão) ou 'image_base64' (compatibilidade legado)
        file_base64 = req_body.get('image_base64') or req_body.get('file_base64')
        expected_type = req_body.get('expected_type')
        # Nome do arquivo é crucial para definir se é PDF, DOCX ou Imagem
        file_name = req_body.get('file_name', 'arquivo_desconhecido.jpg')

        # 3. Limpeza do Base64 (Sanitização)
        # Frontends web enviam "data:application/pdf;base64,JVBERi..."
        # Precisamos remover o cabeçalho antes da vírgula.
        if file_base64 and "," in file_base64:
            file_base64 = file_base64.split(",")[1]

        # Validação de campos obrigatórios
        if not file_base64 or not expected_type:
            return func.HttpResponse(
                json.dumps({
                    "result": "NOK", 
                    "message": "Parâmetros obrigatórios ausentes: 'file_base64' e 'expected_type'."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # 4. Execução do Serviço (O Cérebro)
        # Instancia o serviço que contém as lógicas de Magic Number, Senha, OCR e LLM
        service = DocumentAnalyzerService()
        result = service.validate_document(file_base64, expected_type, file_name)
        
        # 5. Montagem da Resposta
        # O serviço retorna um dicionário com "status": "success" ou "error"
        is_success = result["status"] == "success"
        data_content = result.get("data", {})
        
        response_payload = {
            "result": "OK" if is_success else "NOK",
            "message": result.get("message"), # Mensagens amigáveis (ex: "Remova a senha")
            "detected_type": data_content.get("detected_type", "Não identificado"),
            
            # Metadados para monitoramento
            "method_used": data_content.get("method", "unknown"), # Ex: text_extraction_regex, azure_llm_visual
            "file_processed": file_name,
            "confidence": data_content.get("confidence", "low"),
            
            # Detalhes técnicos (snippet do texto, reasoning da IA)
            "details": data_content
        }

        # 6. Logging Estruturado
        # Ajuda a monitorar no Azure Monitor se estamos gastando muito com LLM ou se o Regex está funcionando
        log_message = f"Arquivo: {file_name} | Resultado: {response_payload['result']} | Método: {response_payload['method_used']} | Msg: {response_payload['message']}"
        
        if is_success:
            logging.info(log_message)
        else:
            logging.warning(log_message)

        # Retornamos 200 OK mesmo para "NOK" (rejeição de negócio), 
        # reservando 4xx/5xx para erros técnicos de requisição ou servidor.
        return func.HttpResponse(
            json.dumps(response_payload),
            status_code=200, 
            mimetype="application/json"
        )

    except Exception as e:
        # Captura erros não tratados (bugs críticos)
        logging.error(f"FATAL ERROR no servidor: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "result": "NOK", 
                "message": "Erro interno crítico no servidor.", 
                "error_details": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )