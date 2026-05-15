import os

from langchain_huggingface import HuggingFaceEmbeddings

from .config import DEFAULT_EMBEDDING_MODEL


def get_embeddings() -> HuggingFaceEmbeddings:
    # En local (offline) usamos archivos locales. 
    # En la nube (producción) permitimos descargar el modelo si no existe.
    is_dev = os.getenv("FLASK_DEBUG", "False") == "True"
    local_only = os.getenv("HF_HUB_OFFLINE", "0") == "1" if not is_dev else True
    
    return HuggingFaceEmbeddings(
        model_name=DEFAULT_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu", "local_files_only": local_only},
        encode_kwargs={"normalize_embeddings": True},
    )
