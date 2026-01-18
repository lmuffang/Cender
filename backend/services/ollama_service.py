"""Ollama AI service for email template generation."""

import requests

from config import settings
from exceptions import OllamaError
from utils.logger import logger


SYSTEM_PROMPT = """Tu es un assistant qui rédige des emails de candidature spontanée en français.

RÈGLES STRICTES:
1. TOUJOURS utiliser {salutation} comme placeholder pour la civilité (sera remplacé par "Monsieur", "Madame" ou "Madame, Monsieur")
2. TOUJOURS utiliser {company} comme placeholder pour le nom de l'entreprise
3. JAMAIS inventer de détails spécifiques sur l'entreprise - utilise des phrases génériques comme "votre entreprise" ou "votre société"
4. Ton professionnel mais naturel
5. Email court: 3-4 paragraphes maximum
6. Mentionner que le CV est en pièce jointe
7. Ne pas utiliser de formules trop formelles ou désuètes
8. Commencer directement par "{salutation}," sur la première ligne

Réponds UNIQUEMENT avec le contenu de l'email, sans explications ni commentaires."""


class OllamaService:
    """Service for interacting with Ollama AI."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.enabled = settings.ollama_enabled

    def check_status(self) -> dict:
        """
        Check if Ollama is running and model is available.

        Returns:
            dict with keys: available, model, model_loaded, error
        """
        if not self.enabled:
            return {
                "available": False,
                "model": self.model,
                "model_loaded": False,
                "error": "Ollama is disabled in configuration",
            }

        try:
            # Check if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return {
                    "available": False,
                    "model": self.model,
                    "model_loaded": False,
                    "error": f"Ollama returned status {response.status_code}",
                }

            # Check if model is available
            models_data = response.json()
            available_models = [m.get("name", "") for m in models_data.get("models", [])]

            # Check for exact match or base name match
            model_loaded = any(
                self.model == m or self.model.split(":")[0] == m.split(":")[0]
                for m in available_models
            )

            return {
                "available": True,
                "model": self.model,
                "model_loaded": model_loaded,
                "error": None if model_loaded else f"Model {self.model} not found. Available: {', '.join(available_models) or 'none'}",
            }

        except requests.exceptions.ConnectionError:
            return {
                "available": False,
                "model": self.model,
                "model_loaded": False,
                "error": "Cannot connect to Ollama. Is it running?",
            }
        except requests.exceptions.Timeout:
            return {
                "available": False,
                "model": self.model,
                "model_loaded": False,
                "error": "Ollama connection timed out",
            }
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
            return {
                "available": False,
                "model": self.model,
                "model_loaded": False,
                "error": str(e),
            }

    def generate_template(self, user_context: str | None = None) -> dict:
        """
        Generate an email template using Ollama.

        Args:
            user_context: Optional context about the user (skills, experience, etc.)

        Returns:
            dict with keys: content, subject, model_used

        Raises:
            OllamaError: If generation fails
        """
        if not self.enabled:
            raise OllamaError("Ollama is disabled in configuration")

        # Build the user prompt
        user_prompt = "Rédige un email de candidature spontanée."
        if user_context:
            user_prompt += f"\n\nContexte sur le candidat:\n{user_context}"

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                    },
                },
                timeout=self.timeout,
            )

            if response.status_code != 200:
                error_msg = f"Ollama returned status {response.status_code}"
                try:
                    error_detail = response.json().get("error", "")
                    if error_detail:
                        error_msg += f": {error_detail}"
                except Exception:
                    pass
                raise OllamaError(error_msg)

            result = response.json()
            content = result.get("response", "").strip()

            if not content:
                raise OllamaError("Ollama returned empty response")

            # Generate a default subject
            subject = "Candidature spontanée - {company}"

            logger.info(f"Generated AI template using model {self.model}")

            return {
                "content": content,
                "subject": subject,
                "model_used": self.model,
            }

        except requests.exceptions.ConnectionError:
            raise OllamaError("Cannot connect to Ollama. Is it running?")
        except requests.exceptions.Timeout:
            raise OllamaError(f"Ollama request timed out after {self.timeout}s")
        except OllamaError:
            raise
        except Exception as e:
            logger.error(f"Error generating template with Ollama: {e}")
            raise OllamaError(f"Failed to generate template: {e}")


# Global service instance
_ollama_service: OllamaService | None = None


def get_ollama_service() -> OllamaService:
    """Get or create the Ollama service instance."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
