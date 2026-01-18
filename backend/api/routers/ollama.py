"""Ollama AI endpoints for email template generation."""

from fastapi import APIRouter

from api.schemas import AITemplateRequest, AITemplateResponse, OllamaStatusResponse
from services.ollama_service import get_ollama_service

router = APIRouter(tags=["ollama"])


@router.get("/ollama/status", response_model=OllamaStatusResponse)
async def get_ollama_status():
    """Check Ollama availability and model status."""
    service = get_ollama_service()
    return service.check_status()


@router.post("/users/{user_id}/generate-ai-template", response_model=AITemplateResponse)
async def generate_ai_template(user_id: int, request: AITemplateRequest):
    """Generate an AI email template using Ollama."""
    service = get_ollama_service()
    return service.generate_template(request.user_context)
