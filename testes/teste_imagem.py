import base64

# Caminho da sua imagem
path = r"C:/Users/z3xai/Downloads/o-que-e-cpf-1-768x490-cópia.jpg"

with open(path, "rb") as img:
    b64 = base64.b64encode(img.read()).decode('utf-8')
    
    # Salva num arquivo de texto para facilitar o copiar/colar
    with open("imagem_base64.txt", "w") as f:
        f.write(b64)
        
print("✅ Base64 salvo no arquivo 'imagem_base64.txt'. Pode copiar de lá.")