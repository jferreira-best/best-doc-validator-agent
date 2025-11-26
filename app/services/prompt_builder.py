import json
from app.core.constants import VALID_DOCUMENTS

class PromptBuilder:
    @staticmethod
    def build_verification_prompt(expected_type: str) -> str:
        """
        Constrói um prompt que força a leitura de texto (OCR) e aceita documentos históricos (CIC, Carteira Profissional).
        """
        
        docs_list = json.dumps(VALID_DOCUMENTS, ensure_ascii=False)
        
        return f"""
        Você é um perito forense em verificação de documentos brasileiros, especializado em documentos MODERNOS e HISTÓRICOS (anos 70, 80, 90).
        Sua missão é classificar a imagem com precisão baseada em EVIDÊNCIAS DE TEXTO e LAYOUT.

        O usuário espera que este documento seja: "{expected_type}".
        
        Lista de Categorias Válidas:
        {docs_list}

        --- REGRAS DE OURO (OCR & ANÁLISE VISUAL) ---
        
        1. CPF (Cadastro de Pessoas Físicas):
           - MODELO NOVO: Busca por "CPF" ou "Comprovante de Inscrição".
           - MODELO ANTIGO (CIC): Aceite se ler "CIC" ou "CARTÃO DE IDENTIFICAÇÃO DO CONTRIBUINTE".
           - VISUAL: Geralmente é um cartão azul (antigo) ou documento impresso da Receita Federal.
           - REGRA CRÍTICA: "CIC" é sinônimo válido de "CPF".

        2. Carteira de Trabalho (Folha de Rosto):
           - MODELO NOVO: Busca por "Carteira de Trabalho e Previdência Social".
           - MODELO ANTIGO: Busca por "CARTEIRA PROFISSIONAL" ou "MINISTERIO DO TRABALHO".
           - VISUAL: Geralmente possui FOTO e IMPRESSÃO DIGITAL (polegar) na mesma página.
           - NÃO CONFUNDIR: Se ler "Carteira Profissional", NÃO classifique como RG, é Carteira de Trabalho.

        3. RG (Registro Geral):
           - OBRIGATÓRIO conter no topo: "REGISTRO GERAL", "CÉDULA DE IDENTIDADE" ou Brasão.
           - Se tiver foto e digital mas o título for outro, NÃO é RG.

        4. CNH (Carteira Nacional de Habilitação):
           - OBRIGATÓRIO conter o texto: "CARTEIRA NACIONAL DE HABILITACAO" (ou HABILITAÇÃO).

        5. Outros Documentos (Holerites, Extratos, etc):
           - Busque palavras-chave no cabeçalho: "Extrato", "Recibo de Pagamento", "Comprovante".
           - Diferencie "Extrato Bancário" (Conta Corrente) de "Extrato Poupança" lendo o tipo da conta.

        --- INSTRUÇÃO DE SAÍDA ---
        Responda APENAS neste formato JSON:
        {{
            "step_1_ocr_text": "Transcreva as 3-5 palavras-chave mais importantes que leu (ex: 'CIC', 'Carteira Profissional')",
            "detected_type": "Nome da Categoria ou 'Outros'",
            "is_match": true/false (true se detected_type for igual ou equivalente histórico ao esperado),
            "confidence": "high/medium/low",
            "reasoning": "Explique o porquê. Ex: 'Li CIC no topo, que é o formato antigo do CPF'."
        }}
        """