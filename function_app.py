import azure.functions as func
import logging
import json
from app.services.llm_service import DocumentAnalyzerService

# Inicializa o App da Function
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="validate_document", methods=["POST"])
def validate_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processando validação de documento via IA.')

    try:
        # 1. Obter dados do corpo da requisição
        req_body = req.get_json()
        image_base64 = req_body.get('image_base64')
        expected_type = req_body.get('expected_type')

        if not image_base64 or not expected_type:
            return func.HttpResponse(
                json.dumps({"result": "NOK", "message": "Faltam dados (image_base64 ou expected_type)"}),
                status_code=400,
                mimetype="application/json"
            )

        # 2. Chamar seu Serviço de IA (Reutilizando a lógica existente)
        service = DocumentAnalyzerService()
        result = service.validate_document(image_base64, expected_type)

        # 3. Mapear resposta para OK / NOK
        # Se o serviço retornou "success", é OK. Caso contrário, NOK.
        if result["status"] == "success":
            response_payload = {
                "result": "OK",
                "detected_type": result.get("data", {}).get("detected_type"),
                "reasoning": result.get("data", {}).get("reasoning") # Útil para auditoria
            }
            status_code = 200
        else:
            response_payload = {
                "result": "NOK",
                "detected_type": result.get("data", {}).get("detected_type", "Desconhecido"),
                "reasoning": result.get("data", {}).get("reasoning", result.get("message"))
            }
            # Retornamos 200 mesmo em NOK porque a requisição funcionou, 
            # apenas o documento foi rejeitado pela regra de negócio.
            status_code = 200 

        return func.HttpResponse(
            json.dumps(response_payload),
            status_code=status_code,
            mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({"result": "NOK", "message": "JSON inválido no corpo da requisição"}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Erro interno: {str(e)}")
        return func.HttpResponse(
            json.dumps({"result": "NOK", "message": f"Erro interno do servidor: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )