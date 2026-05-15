import os

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import DEFAULT_EMBEDDING_MODEL


def get_embeddings() -> HuggingFaceEmbeddings:
    local_only = os.getenv("HF_HUB_OFFLINE", "1") == "1"
    return HuggingFaceEmbeddings(
        model_name=DEFAULT_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu", "local_files_only": local_only},
        encode_kwargs={"normalize_embeddings": True},
    )
