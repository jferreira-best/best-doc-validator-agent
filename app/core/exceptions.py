class DocumentValidationError(Exception):
    """Exceção levantada quando o documento não corresponde ao esperado."""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class LLMProcessingError(Exception):
    """Exceção levantada quando falha a comunicação com a OpenAI."""
    pass