import os
from typing import Any

from langchain_openai import OpenAIEmbeddings

from .config import DEFAULT_EMBEDDING_MODEL

# Variable global para cachear el modelo y no saturar la RAM
_embeddings_instance: Any = None


def get_embeddings() -> Any:
    """
    Obtiene la instancia de embeddings de OpenAI. 
    Se elimina el soporte local (HuggingFace/Torch) para garantizar 
    el funcionamiento en servidores con poca RAM (Render Free).
    """
    global _embeddings_instance
    
    if _embeddings_instance is not None:
        return _embeddings_instance

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "tu_clave":
        raise ValueError("Para funcionar en la nube sin errores de memoria, debes configurar OPENAI_API_KEY en el panel de Render.")

    _embeddings_instance = OpenAIEmbeddings(model="text-embedding-3-small")
    return _embeddings_instance
