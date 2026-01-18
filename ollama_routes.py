"""
Ollama LLM Integration Routes
Connects Reactor AI to Ollama on home rig (10.0.0.3:11434)
Provides chat, completion, and RAG-enhanced inference
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import os
from auth_middleware import verify_api_key

router = APIRouter(prefix="/api/ollama", tags=["ollama"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://10.0.0.3:11434")

class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    context: Optional[List[str]] = None  # RAG context chunks

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    context: Optional[List[str]] = None  # RAG context chunks

@router.get("/models")
async def list_models(api_key: str = Depends(verify_api_key)):
    """List all available Ollama models on home rig"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return {
                "models": [
                    {
                        "name": m["name"],
                        "size": m.get("size", 0),
                        "digest": m.get("digest", ""),
                        "modified_at": m.get("modified_at", "")
                    }
                    for m in models
                ],
                "count": len(models)
            }
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama service unavailable: {str(e)}")

@router.post("/chat")
async def chat_completion(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    """Chat completion with RAG context support"""
    try:
        messages = []
        if request.context:
            context_text = "\n\n".join([f"Document {i+1}:\n{chunk}" for i, chunk in enumerate(request.context)])
            messages.append({"role": "system", "content": f"Context:\n\n{context_text}\n\nUse this to answer questions."})
        messages.extend([{"role": m.role, "content": m.content} for m in request.messages])
        
        payload = {
            "model": request.model,
            "messages": messages,
            "stream": request.stream,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens}
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {str(e)}")

@router.post("/complete")
async def text_completion(request: CompletionRequest, api_key: str = Depends(verify_api_key)):
    """Text completion with RAG context support"""
    try:
        prompt = request.prompt
        if request.context:
            context_text = "\n\n".join([f"Document {i+1}:\n{chunk}" for i, chunk in enumerate(request.context)])
            prompt = f"Context:\n\n{context_text}\n\n---\n\n{prompt}"
        
        payload = {
            "model": request.model,
            "prompt": prompt,
            "stream": request.stream,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens}
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {str(e)}")

@router.get("/health")
async def ollama_health(api_key: str = Depends(verify_api_key)):
    """Check Ollama service health"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            return {"status": "online", "base_url": OLLAMA_BASE_URL, "models_available": len(response.json().get("models", []))}
    except Exception as e:
        return {"status": "offline", "base_url": OLLAMA_BASE_URL, "error": str(e)}
