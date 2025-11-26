import streamlit as st
import requests
import base64

# --- Configurações ---
# URL da Azure Function rodando localmente (Porta padrão 7071)
API_URL = "http://localhost:7071/api/validate_document"

# Lista exata de documentos suportados
DOC_TYPES = [
    "Extrato Bancário",
    "Holerite",
    "Carteira de Trabalho (Último Registro)",
    "Carteira de Trabalho (Folha de Rosto)",
    "Declaração de Imposto de Renda",
    "Extrato Poupança ou Aplicação",
    "Extrato de Aposentadoria ou Pensão",
    "Comprovante de Bolsa Família ou BPC",
    "Extrato do Seguro-Desemprego",
    "RG",
    "CPF",
    "Comprovante de Endereço",
    "Nota Fiscal de Medicamentos",
    "Relatório Médico",
    "RG de Idoso",
    "CNH de Idoso",
    "Extrato do INSS",
    "Outros"
]

st.set_page_config(
    page_title="Validador de Documentos (Azure)",
    page_icon="☁️",
    layout="centered"
)

# --- Funções Auxiliares ---
def encode_image_to_base64(uploaded_file):
    """Lê o arquivo enviado e converte para string Base64."""
    try:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode('utf-8')
        return base64_str
    except Exception as e:
        st.error(f"Erro ao processar imagem: {e}")
        return None

# --- Interface Principal ---
def main():
    st.title("☁️ Validador Azure Functions")
    st.markdown(
        """
        <div style='background-color: #e1f5fe; padding: 10px; border-radius: 5px; margin-bottom: 20px; color: #0277bd;'>
            <p style='margin:0;'>
                Este sistema utiliza <strong>Azure OpenAI (GPT-4o)</strong> via <strong>Azure Functions</strong>.
                Faça upload da imagem para validar a regra de negócio (OK / NOK).
            </p>
        </div>
        """, unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        expected_type = st.selectbox(
            "🏷️ Tipo esperado:",
            options=DOC_TYPES,
            index=DOC_TYPES.index("RG") if "RG" in DOC_TYPES else 0
        )

    with col2:
        uploaded_file = st.file_uploader(
            "🖼️ Upload da imagem",
            type=["jpg", "jpeg", "png"],
            help="Formatos aceitos: JPG, PNG."
        )

    if uploaded_file is not None:
        st.divider()
        st.subheader("Resultado da Validação")
        
        st.image(uploaded_file, caption=f"Analisando como: {expected_type}", width=400)

        validate_button = st.button("🚀 Enviar para Azure Function", type="primary", use_container_width=True)

        if validate_button:
            with st.spinner(f"☁️ Conectando na Azure Function..."):
                base64_img = encode_image_to_base64(uploaded_file)

                if base64_img:
                    payload = {
                        "expected_type": expected_type,
                        "image_base64": base64_img
                    }

                    try:
                        # Chama a URL da Azure Function (Porta 7071)
                        response = requests.post(API_URL, json=payload, timeout=60)
                        response.raise_for_status()
                        
                        result = response.json()

                        # --- Exibição dos Resultados (Adaptado para Schema OK/NOK) ---
                        st.divider()

                        # Verifica se o resultado é OK
                        if result.get("result") == "OK":
                            st.success("✅ Documento APROVADO (OK)")
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Status", "OK", delta="Aprovado")
                            c2.metric("Tipo Detectado", result.get("detected_type"))

                            st.info(f"💡 **Raciocínio da IA:** {result.get('reasoning')}")
                            st.balloons()
                            
                        else:
                            # Caso seja NOK
                            st.error(f"❌ Documento REJEITADO (NOK)")
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Status", "NOK", delta="- Rejeitado", delta_color="inverse")
                            c2.metric("Tipo Detectado", result.get("detected_type", "Desconhecido"))

                            st.warning(f"⚠️ **Motivo:** {result.get('reasoning')}")

                        # Debug opcional para ver o JSON cru
                        with st.expander("🔍 Ver JSON de Resposta"):
                            st.json(result)

                    except requests.exceptions.ConnectionError:
                        st.error("⛔ Erro de Conexão: Não foi possível conectar na Azure Function.")
                        st.markdown("**Dica:** Verifique se você rodou `func start` no terminal e se a porta é `7071`.")
                    except requests.exceptions.Timeout:
                        st.error("⏱️ Timeout: A Azure Function demorou muito para responder.")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Erro na requisição: {e}")

if __name__ == "__main__":
    main()