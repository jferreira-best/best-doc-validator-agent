import azure.functions as func
import logging
import json
# import base64  <-- Não precisa mais, já vem pronto do front
from app.services.llm_service import DocumentAnalyzerService

app = func.FunctionApp()

@app.function_name(name="validate_document")
@app.route(route="validate_document", auth_level=func.AuthLevel.ANONYMOUS, methods=['POST'])
def validate_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Requisição recebida: Processando JSON do Streamlit.')

    try:
        # 1. Tenta pegar o JSON (Já que o Streamlit manda json=payload)
        try:
            req_body = req.get_json()
        except ValueError:
             return func.HttpResponse(
                json.dumps({"result": "NOK", "message": "O corpo da requisição não é um JSON válido."}),
                status_code=400,
                mimetype="application/json"
            )

        # 2. Extrai os dados usando as CHAVES EXATAS do seu main.py
        # No main.py você usou: "file_base64", "expected_type", "file_name"
        #base64_string = req_body.get('file_base64')
        base64_string = req_body.get('file_base64') or req_body.get('image_base64')
        expected_type = req_body.get('expected_type')
        file_name = req_body.get('file_name', 'arquivo_sem_nome')

        # Validação Básica
        if not base64_string or not expected_type:
            return func.HttpResponse(
                json.dumps({
                    "result": "NOK", 
                    "message": "Faltando dados. O JSON deve ter 'file_base64' e 'expected_type'."
                }),
                status_code=400,
                mimetype="application/json"
            )

        logging.info(f"Processando arquivo: {file_name} | Tipo esperado: {expected_type}")

        # 3. Execução do Serviço
        # Note que removi a conversão de binário para base64, pois já recebemos a string pronta!
        service = DocumentAnalyzerService()
        
        # Passamos direto a string que veio do front
        result = service.validate_document(base64_string, expected_type, file_name)
        
        # 4. Montagem da Resposta
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
            json.dumps({"result": "NOK", "message": "Erro interno no Backend.", "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )