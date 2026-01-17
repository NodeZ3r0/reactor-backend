from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.get("/status")
async def status():
    return {
        "api": "online",
        "mcp": "online",
        "spec_kit": "online",
        "rag": "online",
        "db": "online",
        "ollama": "online",
        "forgejo": "online"
    }

@router.get("/models")
async def models():
    return {
        "models": []
    }

@router.get("/tasks")
async def tasks():
    return []
