import uvicorn
import os
import sys

# Garante que o diretório atual esteja no path do Python
# Isso previne erros de "ModuleNotFoundError: No module named 'app'"
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

if __name__ == "__main__":
    # Mensagens de ajuda no terminal
    print("----------------------------------------------------------------")
    print(f"🚀 Iniciando Backend do Validador de Documentos...")
    print(f"📡 API disponível em: http://localhost:{settings.PORT}")
    print(f"📄 Documentação Swagger: http://localhost:{settings.PORT}/docs")
    print("----------------------------------------------------------------")

    # Inicia o servidor Uvicorn
    uvicorn.run(
        "app.main:app",          # Aponta para a instância 'app' dentro de app/main.py
        host="0.0.0.0",          # Permite acesso externo (útil se usar Docker depois)
        port=settings.PORT,      # Pega a porta definida no .env ou default (8000)
        reload=True,             # Reinicia automaticamente ao salvar arquivos (modo dev)
        log_level="info"
    )