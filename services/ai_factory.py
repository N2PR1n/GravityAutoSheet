import os
from .openai_service import OpenAIService
from .gemini_service import GeminiService

class AIFactory:
    @staticmethod
    def get_service(provider, api_key_openai=None, api_key_gemini=None):
        """
        Returns the appropriate AI service instance based on the provider.
        """
        provider = provider.lower() if provider else "openai"
        
        if provider == "gemini":
            if not api_key_gemini:
                api_key_gemini = os.getenv('GEMINI_API_KEY')
            return GeminiService(api_key_gemini)
        else:
            # Default to OpenAI
            if not api_key_openai:
                api_key_openai = os.getenv('OPENAI_API_KEY')
            return OpenAIService(api_key_openai)
