# Reactor AI Backend Changelog

## 2026-01-18 - RAG System Improvements

### Enhanced RAG System Prompts
- Updated `/api/ollama/chat` endpoint with comprehensive system prompts for RAG context
- LLM now receives clear instructions on how to use retrieved documents
- System prompt includes:
  - Explicit instruction to use context documents
  - Guidance on citing sources and listing documents
  - Clear fallback behavior when context lacks information
  
### Previous Updates
- Added Forgejo health check integration
- Ollama LLM integration (11 models available)
- RAG document ingestion and query endpoints
- Multi-service health monitoring

