import os
from typing import Any
import logging
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from .config import DEFAULT_EMBEDDING_MODEL

# Configuración de logs para este módulo
logger = logging.getLogger(__name__)

# Variable global para cachear el modelo y no saturar la RAM
_embeddings_instance: Any = None

def get_embeddings() -> Any:
    """
    Obtiene la instancia de embeddings. Prioriza OpenAI si hay clave,
    de lo contrario usa HuggingFace local.
    """
    global _embeddings_instance
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key and api_key != "tu_clave" and len(api_key) > 10:
        if _embeddings_instance is None or not isinstance(_embeddings_instance, OpenAIEmbeddings):
            logger.info("Usando OpenAIEmbeddings (Mayor precisión)")
            _embeddings_instance = OpenAIEmbeddings(model="text-embedding-3-small")
        return _embeddings_instance

    if _embeddings_instance is not None:
        return _embeddings_instance

    logger.info(f"Inicializando modelo de embeddings local: {DEFAULT_EMBEDDING_MODEL}")
    _embeddings_instance = HuggingFaceEmbeddings(
        model_name=DEFAULT_EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'}
    )
    return _embeddings_instance
