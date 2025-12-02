import requests
import json

# URL da sua Function no Azure (baseado no nome que vi nos seus logs)
FUNCTION_URL = "https://af-atendimento-validarDocumento-dev.azurewebsites.net/api/validate_document"

# Um pixel branco em Base64 (só para não quebrar a validação básica de string)
DUMMY_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="

payload = {
    "expected_type": "RG",  # Testando se ele aceita o fluxo
    "file_name": "teste_conexao.jpg",
    "image_base64": DUMMY_IMAGE
}

print(f"📡 Disparando teste para: {FUNCTION_URL} ...")

try:
    response = requests.post(FUNCTION_URL, json=payload, timeout=60)
    
    print(f"\nStatus Code: {response.status_code}")
    
    try:
        print("Resposta JSON:", json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print("Resposta Texto (não-JSON):", response.text)

    if response.status_code == 200:
        print("\n✅ SUCESSO! A Function está ativa e respondendo.")
    elif response.status_code == 404:
        print("\n❌ ERRO 404: A Function não foi encontrada. O deploy subiu os arquivos, mas o Azure não indexou a função.")
    elif response.status_code == 500:
        print("\n🔥 ERRO 500: A Function caiu ao tentar processar. Provavelmente erro de importação ou chave de API errada no servidor.")

except Exception as e:
    print(f"\n☠️ Erro ao conectar: {str(e)}")