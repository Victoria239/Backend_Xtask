"""RAG service - retrieval-augmented generation infrastructure (AI-01, AI-02, Q4-9)."""
import os

# Dimensión del vector — debe matchear el modelo de embeddings activo:
#   - nomic-embed-text (Ollama, default): 768
#   - text-embedding-3-small (OpenAI):    1536
#   - text-embedding-3-large (OpenAI):    3072
# Configurable vía env. Cambiar requiere DROP svc_rag.chunks (vector dim no se altera in-place).
EMBEDDING_DIM: int = int(os.environ.get("EMBEDDING_DIM", "768"))
