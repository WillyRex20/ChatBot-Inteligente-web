import os
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from .config import DEFAULT_EMBEDDING_MODEL

# Variable global para cachear el modelo y no saturar la RAM
_embeddings_instance: Any = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Obtiene la instancia de embeddings. Prioriza OpenAI si la API Key está presente
    para ahorrar memoria RAM en servidores como Render.
    """
    global _embeddings_instance
    
    if _embeddings_instance is not None:
        return _embeddings_instance

    api_key = os.getenv("OPENAI_API_KEY")
    
    # Si hay API Key válida, usamos OpenAI (consume casi 0 RAM en el servidor)
    if api_key and api_key != "tu_clave":
        _embeddings_instance = OpenAIEmbeddings(model="text-embedding-3-small")
        return _embeddings_instance

    # Si no hay API Key, cargamos el modelo local (consume mucha RAM)
    # En la nube (producción) permitimos descargar el modelo si no existe.
    is_dev = os.getenv("FLASK_DEBUG", "False") == "True"
    local_only = os.getenv("HF_HUB_OFFLINE", "0") == "1" if not is_dev else True
    
    _embeddings_instance = HuggingFaceEmbeddings(
        model_name=DEFAULT_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu", "local_files_only": local_only},
        encode_kwargs={"normalize_embeddings": True},
    )
    return _embeddings_instance
