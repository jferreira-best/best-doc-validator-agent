import azure.functions as func
import logging
import json
import base64
from app.services.llm_service import DocumentAnalyzerService

app = func.FunctionApp()

@app.function_name(name="validate_document")
@app.route(route="validate_document", auth_level=func.AuthLevel.ANONYMOUS, methods=['POST'])
def validate_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Requisição recebida: Upload de Arquivo (Multipart).')

    try:
        # 1. Tenta pegar o arquivo do formulário multipart
        # O nome do campo no Postman/Frontend deve ser 'file'
        input_file = req.files.get('file')
        
        # 2. Pega os metadados do formulário (não é mais JSON Body)
        expected_type = req.form.get('expected_type')
        
        # Fallback: Se o client mandar o nome do arquivo, usamos. Se não, pegamos do próprio arquivo.
        file_name = req.form.get('file_name')
        if not file_name and input_file:
            file_name = input_file.filename

        # Validação Básica
        if not input_file or not expected_type:
            return func.HttpResponse(
                json.dumps({
                    "result": "NOK", 
                    "message": "Parâmetros obrigatórios ausentes. Envie 'file' (arquivo) e 'expected_type' (texto) via form-data."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # 3. Conversão Binário -> Base64 (Para manter compatibilidade com seu LLM Service)
        # Lemos o arquivo da memória
        file_bytes = input_file.read()
        
        # Verificação de tamanho (Opcional, mas recomendado para proteger a Function)
        tamanho_mb = len(file_bytes) / (1024 * 1024)
        logging.info(f"Processando arquivo: {file_name} | Tamanho: {tamanho_mb:.2f} MB")

        # Converte para Base64 string
        base64_string = base64.b64encode(file_bytes).decode('utf-8')

        # 4. Execução do Serviço (Igual ao anterior)
        service = DocumentAnalyzerService()
        result = service.validate_document(base64_string, expected_type, file_name)
        
        # 5. Montagem da Resposta (Igual ao anterior)
        is_success = result["status"] == "success"
        data_content = result.get("data", {})
        
        response_payload = {
            "result": "OK" if is_success else "NOK",
            "message": result.get("message"),
            "detected_type": data_content.get("detected_type", "Não identificado"),
            "file_processed": file_name,
            "details": data_content
        }

        return func.HttpResponse(
            json.dumps(response_payload),
            status_code=200, 
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Erro crítico: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"result": "NOK", "message": "Erro interno.", "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )