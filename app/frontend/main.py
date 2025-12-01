import streamlit as st
import requests
import base64
import uuid

# --- Configurações ---
API_URL = "http://localhost:7071/api/validate_document"

DOC_TYPES = [
    "Extrato Bancário", "Holerite", "Carteira de Trabalho (Último Registro)",
    "Carteira de Trabalho (Folha de Rosto)", "Declaração de Imposto de Renda",
    "Extrato Poupança ou Aplicação", "Extrato de Aposentadoria ou Pensão",
    "Comprovante de Bolsa Família ou BPC", "Extrato do Seguro-Desemprego",
    "RG", "CPF", "Comprovante de Endereço", "Nota Fiscal de Medicamentos",
    "Relatório Médico", "RG de Idoso", "CNH de Idoso", "Extrato do INSS", "Outros"
]

st.set_page_config(page_title="Validador de Documentos", page_icon="☁️", layout="centered")

# --- Gerenciamento de Estado ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = str(uuid.uuid4())

if 'selectbox_key' not in st.session_state:
    st.session_state.selectbox_key = str(uuid.uuid4())

def reset_form():
    st.session_state.uploader_key = str(uuid.uuid4())
    st.session_state.selectbox_key = str(uuid.uuid4())

# --- Funções Auxiliares ---
def encode_file_to_base64(uploaded_file):
    """Converte qualquer arquivo (PDF, Imagem, Docx) para Base64."""
    try:
        bytes_data = uploaded_file.getvalue()
        return base64.b64encode(bytes_data).decode('utf-8')
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
        return None

# --- Interface Principal ---
def main():
    st.title("☁️ Validador Azure Functions")
    
    st.markdown(
        """
        <div style='background-color: #e1f5fe; padding: 10px; border-radius: 5px; margin-bottom: 20px; color: #0277bd;'>
            <p style='margin:0;'>Sistema Híbrido: <strong>OCR (Visão/Texto)</strong> + <strong>OpenAI</strong>.</p>
        </div>
        """, unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        expected_type = st.selectbox(
            "🏷️ Tipo esperado:",
            options=DOC_TYPES,
            index=DOC_TYPES.index("RG") if "RG" in DOC_TYPES else 0,
            key=st.session_state.selectbox_key
        )

    with col2:
        # --- AJUSTE 1: Adicionado "pdf" e "docx" na lista de tipos permitidos ---
        uploaded_file = st.file_uploader(
            "📄 Upload do documento",
            type=["jpg", "jpeg", "png", "pdf", "docx"], 
            help="Aceita: Imagens, PDF e Word.",
            key=st.session_state.uploader_key
        )

    if uploaded_file is not None:
        st.divider()
        st.subheader("Pré-visualização")

        # --- AJUSTE 2: Só tenta mostrar imagem se for imagem ---
        # Se for PDF ou DOCX, mostra apenas o nome do arquivo para não quebrar o app
        file_type = uploaded_file.name.split('.')[-1].lower()
        
        if file_type in ['jpg', 'jpeg', 'png']:
            st.image(uploaded_file, caption=f"Analisando: {expected_type}", width=400)
        else:
            st.info(f"📄 **Arquivo carregado:** {uploaded_file.name} (Formato: {file_type.upper()})")
            st.caption("O conteúdo deste arquivo será extraído e analisado via texto.")

        validate_button = st.button("🚀 Enviar para Análise", type="primary", use_container_width=True)

        if validate_button:
            with st.spinner(f"☁️ Processando {file_type.upper()} na Azure..."):
                base64_str = encode_file_to_base64(uploaded_file)

                if base64_str:
                    # --- AJUSTE 3: Envia o file_name para o backend saber a extensão ---
                    payload = {
                        "expected_type": expected_type,
                        "file_base64": base64_str, # Nome atualizado para ser genérico
                        "file_name": uploaded_file.name
                    }

                    try:
                        response = requests.post(API_URL, json=payload, timeout=90) # Aumentei timeout para PDFs grandes
                        response.raise_for_status()
                        result = response.json()

                        st.divider()
                        result_container = st.container()
                        
                        with result_container:
                            if result.get("result") == "OK":
                                st.success("✅ Documento APROVADO")
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Status", "OK", delta="Aprovado")
                                c2.metric("Tipo", result.get("detected_type"))
                                c3.metric("Método", result.get("method_used", "IA"))
                                
                                st.info(f"💡 **Detalhes:** {result.get('details', {}).get('reasoning', 'Sem detalhes adicionais.')}")
                                st.balloons()
                            else:
                                st.error(f"❌ Documento REJEITADO")
                                c1, c2 = st.columns(2)
                                c1.metric("Status", "NOK", delta="- Rejeitado", delta_color="inverse")
                                c2.metric("Tipo Detectado", result.get("detected_type", "Desconhecido"))
                                st.warning(f"⚠️ **Motivo:** {result.get('message')}")

                            with st.expander("🔍 Ver JSON Técnico"):
                                st.json(result)

                    except Exception as e:
                        st.error(f"Erro na comunicação: {e}")

        st.divider()
        if st.button("🔄 Nova Validação (Limpar)", use_container_width=True):
            reset_form()
            st.rerun()

if __name__ == "__main__":
    main()